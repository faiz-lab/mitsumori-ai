from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from openai import OpenAI

from .ocr_backend import OCRError, ocr_pages
from .match import DatabaseMatcher

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

JSON_EXTRACT_INSTRUCTIONS = """
以下のOCRテキストから照明カタログの品番/型番になり得る候補を抽出してください。\n\n【タスク】\n- 品番に見える文字列を抽出し、JSON配列で出力してください。\n- 各要素は {"hinban": "元の表記", "normalized": "正規化後"} の形式にしてください。\n- normalized は NFKC で全角→半角、空白除去、アルファベット大文字化を施してください。\n- 例："NNF41030 LE9" -> {"hinban": "NNF41030 LE9", "normalized": "NNF41030LE9"}\n- 普通の単語・純粋な数字のみの並び・意味不明な短い文字列は除外してください。\n- OCRにより分断された場合は結合してください。(例: "NNF 41030" -> "NNF41030")\n- 出力は JSON 配列のみとし、余計な説明文は付けないでください。\n"""

REGEX_PATTERN = re.compile(r"[A-Z]{1,5}\d{2,6}[A-Z0-9]*")


@dataclass
class MatchResult:
    input_hinban: str
    normalized: str
    match_status: str
    score: float
    matched_hinban: str | None = None
    page: int | None = None
    confidence: float | None = None


def _normalize_candidate(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    text = re.sub(r"\s+", "", text)
    return text.upper()


def _unique_items(items: Iterable[dict]) -> List[dict]:
    unique: dict[str, dict] = {}
    for item in items:
        hinban = str(item.get("hinban", "")).strip()
        normalized = _normalize_candidate(item.get("normalized", hinban))
        if not normalized:
            continue
        if normalized not in unique:
            unique[normalized] = {"hinban": hinban, "normalized": normalized}
    return list(unique.values())


def extract_hinbans_with_gpt(
    text: str,
    model: str,
    base_url: str,
    api_key: str,
    timeout: int,
) -> list[dict]:
    client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
    truncated_text = text[:8000]
    user_prompt = f"{JSON_EXTRACT_INSTRUCTIONS}\nOCRテキスト:\n```\n{truncated_text}\n```"
    messages = [
        {
            "role": "system",
            "content": "あなたはOCR後の照明カタログから品番を抽出する日本語テキスト解析エンジンです。",
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    backoff = 1.5
    attempt = 0
    max_attempts = 3
    while attempt < max_attempts:
        attempt += 1
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=messages,
            )
            content = response.choices[0].message.content if response.choices else ""
            if not content:
                logger.warning("モデルの応答が空でした。正規表現にフォールバックします。")
                return _fallback_regex_extraction(text)
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                logger.warning("JSONの解析に失敗しました。正規表現にフォールバックします。")
                return _fallback_regex_extraction(text)
            if not isinstance(parsed, list):
                logger.warning("モデル応答がJSON配列ではありません。正規表現にフォールバックします。")
                return _fallback_regex_extraction(text)
            normalized_items = _unique_items(parsed)
            if not normalized_items:
                logger.info("モデルから有効な品番が得られませんでした。正規表現にフォールバックします。")
                return _fallback_regex_extraction(text)
            return normalized_items
        except Exception as exc:  # pragma: no cover - depends on network
            status_code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
            if status_code in (429, 500, 502, 503, 504) and attempt < max_attempts:
                sleep_time = backoff ** attempt
                logger.warning(
                    "OpenAI API error (status=%s). Retrying in %.1f seconds...", status_code, sleep_time
                )
                time.sleep(sleep_time)
                continue
            logger.exception("OpenAI API呼び出しに失敗しました。正規表現にフォールバックします。")
            return _fallback_regex_extraction(text)
    return _fallback_regex_extraction(text)


def _fallback_regex_extraction(text: str) -> list[dict]:
    normalized_text = unicodedata.normalize("NFKC", text.upper())
    candidates = []
    for match in REGEX_PATTERN.finditer(normalized_text):
        token = match.group(0)
        normalized = _normalize_candidate(token)
        candidates.append({"hinban": token, "normalized": normalized})
    return _unique_items(candidates)


def _match_semantic_items(
    items: list[dict], matcher: DatabaseMatcher, fuzzy_threshold: float = 0.82
) -> list[MatchResult]:
    all_rows = list(matcher.hinban_map.values())
    results: list[MatchResult] = []
    for item in items:
        hinban = str(item.get("hinban", "")).strip()
        normalized = _normalize_candidate(item.get("normalized", hinban))
        if not normalized:
            continue

        status = "NONE"
        score = 0.0
        matched_hinban: str | None = None

        row = matcher.hinban_map.get(normalized)
        if row:
            status = "EXACT"
            matched_hinban = row.hinban
            score = 1.0
        else:
            for candidate in all_rows:
                if normalized and normalized in candidate.hinban:
                    status = "SUBSTR"
                    matched_hinban = candidate.hinban
                    score = 0.9
                    break
                if candidate.hinban and candidate.hinban in normalized:
                    status = "SUBSTR"
                    matched_hinban = candidate.hinban
                    score = 0.9
                    break

        if status == "NONE":
            retry_candidates = matcher.retry(normalized)
            if retry_candidates:
                status = "KIDOU"
                matched_hinban = retry_candidates[0]
                score = 0.88

        if status == "NONE":
            best_ratio = 0.0
            best_match = None
            for candidate in all_rows:
                ratio = _similarity(normalized, candidate.hinban)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = candidate.hinban
            if best_ratio >= fuzzy_threshold and best_match:
                status = "FUZZY"
                matched_hinban = best_match
                score = round(best_ratio, 3)

        results.append(
            MatchResult(
                input_hinban=hinban,
                normalized=normalized,
                match_status=status,
                score=score,
                matched_hinban=matched_hinban,
            )
        )
    return results


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    from difflib import SequenceMatcher

    return SequenceMatcher(None, a, b).ratio()


def process_pdf_semantic(
    pdf_path: str,
    db_path: str,
    model: str,
    base_url: str,
    api_key: str | None,
    timeout: int,
    save: bool,
) -> pd.DataFrame:
    resolved_base_url = (
        base_url
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("CUSTOM_OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    )
    resolved_api_key = (
        api_key
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("CUSTOM_OPENAI_API_KEY")
    )
    if not resolved_api_key:
        message = "OpenAI APIキーが設定されていません。"
        logger.error(message)
        raise RuntimeError(message)

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        message = f"PDFファイルが見つかりません: {pdf_path}"
        logger.error(message)
        raise RuntimeError(message)

    db_file = Path(db_path)
    if not db_file.exists():
        message = f"CSVファイルが見つかりません: {db_path}"
        logger.error(message)
        raise RuntimeError(message)

    try:
        texts = ocr_pages(str(pdf_file))
    except OCRError as exc:
        message = f"OCR処理に失敗しました: {exc}"
        logger.error(message)
        raise RuntimeError(message) from exc
    except Exception as exc:  # pragma: no cover - unexpected I/O
        message = f"PDFの読み込みに失敗しました: {exc}"
        logger.error(message)
        raise RuntimeError(message) from exc

    ocr_text = "\n".join(texts)
    items = extract_hinbans_with_gpt(
        text=ocr_text,
        model=model,
        base_url=resolved_base_url,
        api_key=resolved_api_key,
        timeout=timeout,
    )

    print("抽出された品番:")
    for item in items:
        print(f"- {item.get('hinban', '')}")

    try:
        matcher = DatabaseMatcher(db_file)
    except ValueError as exc:
        message = str(exc)
        logger.error(message)
        raise RuntimeError(message) from exc

    match_results = _match_semantic_items(items, matcher)

    print("照合結果:")
    for result in match_results:
        matched = result.matched_hinban or "-"
        print(
            f"{result.match_status:<5} | {result.input_hinban:<18} -> {matched:<15} | score={result.score:0.3f}"
        )

    df = pd.DataFrame(
        [
            {
                "input_hinban": r.input_hinban,
                "normalized": r.normalized,
                "match_status": r.match_status,
                "score": r.score,
                "matched_hinban": r.matched_hinban,
                "page": r.page,
                "confidence": r.confidence,
            }
            for r in match_results
        ]
    )

    if save:
        logs_dir = Path("logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = logs_dir / f"match_{timestamp}.csv"
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info("照合結果を保存しました: %s", output_path)

    return df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Semantic matcher for hinban extraction")
    parser.add_argument("--pdf", required=True, help="入力PDFのパス")
    parser.add_argument("--db", required=True, help="品番CSVのパス")
    parser.add_argument("--model", default="gpt-4.1-mini", help="使用するモデル名")
    parser.add_argument("--base-url", default=None, help="OpenAI互換APIのベースURL")
    parser.add_argument("--api-key", default=None, help="OpenAI互換APIのキー")
    parser.add_argument("--timeout", type=int, default=60, help="APIタイムアウト(秒)")
    parser.add_argument("--save", action="store_true", help="結果をCSVに保存")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        process_pdf_semantic(
            pdf_path=args.pdf,
            db_path=args.db,
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
            timeout=args.timeout,
            save=args.save,
        )
    except RuntimeError:
        sys.exit(1)
