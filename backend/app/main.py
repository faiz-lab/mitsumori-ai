from __future__ import annotations

import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .extract import extract_text_pages
from .match import DatabaseMatcher
from .models import (
    FailuresResponse,
    FailureRow,
    RetryRequest,
    RetryResponse,
    ResultRow,
    ResultsResponse,
    StatusResponse,
    StatusTotals,
    UploadResponse,
)
from .ocr_backend import OCRError
from .semantic_match import process_pdf_semantic
from .utils import ensure_storage_dir, extract_tokens, save_upload_file, write_csv

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AI見積システム API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STORAGE_ROOT = Path(__file__).resolve().parent / "storage"
ensure_storage_dir(STORAGE_ROOT)


@dataclass
class TaskState:
    task_id: str
    directory: Path
    totals: StatusTotals = field(default_factory=StatusTotals)
    progress: int = 0
    pages: int = 0
    results: List[ResultRow] = field(default_factory=list)
    failures: List[FailureRow] = field(default_factory=list)
    matcher: DatabaseMatcher | None = None
    error: str | None = None


TASKS: Dict[str, TaskState] = {}


def update_progress(state: TaskState, processed_pages: int) -> None:
    if state.pages == 0:
        state.progress = 0
    else:
        state.progress = min(100, int(processed_pages / state.pages * 100))


def process_task(task_id: str, csv_path: Path, pdf_paths: List[Path]) -> None:
    state = TASKS[task_id]
    try:
        matcher = DatabaseMatcher(csv_path)
        state.matcher = matcher
    except Exception as exc:
        state.error = f"CSVの読み込みに失敗しました: {exc}"
        state.progress = 100
        logger.exception("Failed to load CSV for task %s", task_id)
        return

    total_pages = 0
    for pdf_path in pdf_paths:
        try:
            from PyPDF2 import PdfReader  # type: ignore

            reader = PdfReader(str(pdf_path))
            count = len(reader.pages)
        except Exception:
            count = 0
        total_pages += max(count, 1)
    state.pages = total_pages

    processed_pages = 0
    results: List[ResultRow] = []
    failures: List[FailureRow] = []

    for pdf_path in pdf_paths:
        try:
            page_texts = extract_text_pages(pdf_path)
        except OCRError as exc:
            state.error = str(exc)
            logger.exception("OCR error for %s", pdf_path.name)
            break
        except Exception as exc:
            state.error = f"PDF処理中にエラーが発生しました: {exc}"
            logger.exception("Unexpected error while processing %s", pdf_path.name)
            break

        pdf_name = pdf_path.name
        for page_index, text in enumerate(page_texts, start=1):
            tokens = extract_tokens(text)
            if tokens:
                state.totals.tokens += len(tokens)
            for token in tokens:
                hinban_matches, kidou_matches = matcher.match_token(token)
                matched = False
                for row in hinban_matches:
                    results.append(
                        ResultRow(
                            pdf_name=pdf_name,
                            page=page_index,
                            token=token,
                            matched_type="hinban",
                            matched_hinban=row.hinban,
                            zaiku=row.zaiku,
                        )
                    )
                    state.totals.hit_hinban += 1
                    matched = True
                if kidou_matches:
                    for row in kidou_matches:
                        results.append(
                            ResultRow(
                                pdf_name=pdf_name,
                                page=page_index,
                                token=token,
                                matched_type="spec",
                                matched_hinban=row.hinban,
                                zaiku=row.zaiku,
                            )
                        )
                        state.totals.hit_spec += 1
                        matched = True
                if not matched:
                    failures.append(
                        FailureRow(pdf_name=pdf_name, page=page_index, token=token)
                    )
                    state.totals.fail += 1
            processed_pages += 1
            update_progress(state, processed_pages)

    if state.error:
        state.progress = 100
        state.results = []
        state.failures = []
        return

    results.sort(key=lambda r: (r.pdf_name, r.page, r.matched_type))
    failures.sort(key=lambda r: (r.pdf_name, r.page))

    state.results = results
    state.failures = failures
    state.progress = 100

    results_csv = state.directory / "results.csv"
    failures_csv = state.directory / "failure.csv"

    write_csv(
        results_csv,
        ["pdf_name", "page", "token", "matched_type", "matched_hinban", "zaiku"],
        (
            [r.pdf_name, r.page, r.token, r.matched_type, r.matched_hinban, r.zaiku or ""]
            for r in results
        ),
    )

    write_csv(
        failures_csv,
        ["pdf_name", "page", "token"],
        ([f.pdf_name, f.page, f.token] for f in failures),
    )


@app.post("/api/upload", response_model=UploadResponse)
async def upload(
    background_tasks: BackgroundTasks,
    db_csv: UploadFile = File(...),
    pdfs: List[UploadFile] = File(...),
):
    if not db_csv.filename or not db_csv.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="DB CSVファイル(.csv)を選択してください。")
    if not pdfs:
        raise HTTPException(status_code=400, detail="PDFファイルを少なくとも1件アップロードしてください。")

    task_id = uuid.uuid4().hex
    task_dir = STORAGE_ROOT / task_id
    ensure_storage_dir(task_dir)

    csv_path = task_dir / "database.csv"
    save_upload_file(db_csv, csv_path)

    pdf_paths: List[Path] = []
    for pdf_file in pdfs:
        if not pdf_file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"PDF形式のみ対応しています: {pdf_file.filename}")
        pdf_path = task_dir / pdf_file.filename
        save_upload_file(pdf_file, pdf_path)
        pdf_paths.append(pdf_path)

    state = TaskState(task_id=task_id, directory=task_dir)
    TASKS[task_id] = state
    background_tasks.add_task(process_task, task_id, csv_path, pdf_paths)

    return UploadResponse(task_id=task_id)


@app.get("/api/status/{task_id}", response_model=StatusResponse)
async def get_status(task_id: str):
    state = TASKS.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="該当するタスクが存在しません。")
    if state.error:
        raise HTTPException(status_code=500, detail=state.error)
    return StatusResponse(progress=state.progress, totals=state.totals, pages=state.pages)


@app.get("/api/results/{task_id}", response_model=ResultsResponse)
async def get_results(task_id: str):
    state = TASKS.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="タスクが見つかりません。")
    if state.error:
        raise HTTPException(status_code=500, detail=state.error)
    download_url = f"/api/download/{task_id}?type=results"
    return ResultsResponse(rows=state.results, download_url=download_url)


@app.get("/api/failures/{task_id}", response_model=FailuresResponse)
async def get_failures(task_id: str):
    state = TASKS.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="タスクが見つかりません。")
    if state.error:
        raise HTTPException(status_code=500, detail=state.error)
    download_url = f"/api/download/{task_id}?type=failures"
    return FailuresResponse(rows=state.failures, download_url=download_url)


@app.post("/api/retry", response_model=RetryResponse)
async def retry(request: RetryRequest):
    state = TASKS.get(request.task_id)
    if not state or not state.matcher:
        raise HTTPException(status_code=404, detail="タスクまたはデータが見つかりません。")
    candidates = state.matcher.retry(request.token)
    return RetryResponse(candidates=candidates)


@app.get("/api/download/{task_id}")
async def download_csv(task_id: str, type: str):
    state = TASKS.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="タスクが存在しません。")
    file_map = {
        "results": state.directory / "results.csv",
        "failures": state.directory / "failure.csv",
    }
    if type not in file_map:
        raise HTTPException(status_code=400, detail="typeパラメータが不正です。")
    target = file_map[type]
    if not target.exists():
        raise HTTPException(status_code=404, detail="CSVがまだ生成されていません。")
    return FileResponse(target, media_type="text/csv", filename=target.name)


@app.post("/api/semantic-match")
async def semantic_match_api(
    pdf: UploadFile = File(...),
    csv: UploadFile = File(...),
):
    pdf_path = None
    csv_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as pdf_tmp:
            pdf_tmp.write(await pdf.read())
            pdf_path = pdf_tmp.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as csv_tmp:
            csv_tmp.write(await csv.read())
            csv_path = csv_tmp.name

        base_url = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("CUSTOM_OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        )
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("CUSTOM_OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        timeout = int(os.getenv("OPENAI_TIMEOUT", "60"))

        df = process_pdf_semantic(
            pdf_path=pdf_path,
            db_path=csv_path,
            model=model,
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            save=False,
        )
        return df.to_dict(orient="records")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - unexpected runtime
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if pdf_path and os.path.exists(pdf_path):
            os.unlink(pdf_path)
        if csv_path and os.path.exists(csv_path):
            os.unlink(csv_path)


