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
以下のOCRテキストから照明カタログの品番/型番になり得る候補を抽出してください。
【品番の定義】
- 品番は、2文字または3文字以上のアルファベットから始まります。
- その後に3〜5桁の数字が続きます。
【例】
- ✅ 該当：XNDN1500SLK 
- ✅ 該当：AB12345
- ❌ 非該当：2025-10-07（数字のみ）
- ❌ 非該当：ABC（数字がない）

【タスク】
- 品番に見える文字列を抽出し、以下の関数 `emit_items` を呼び出して返してください。
- normalized は NFKC で全角→半角、空白除去、アルファベット大文字化を施してください。
- 例："NNF41030 LE9" -> {"hinban": "NNF41030 LE9", "normalized": "NNF41030LE9"}
- 普通の単語・純粋な数字のみの並び・意味不明な短い文字列は除外してください。
- OCRにより分断された場合は結合してください。(例: "NNF 41030" -> "NNF41030")
- 出力は関数呼び出しのみとし、説明文は出力しないでください。
"""

REGEX_PATTERN = re.compile(r"[A-Z]{1,5}\d{2,6}[A-Z0-9]*")


@dataclass
class MatchResult:
    input_hinban: str
    normalized: str
    match_status: str
    score: float
    matched_hinban: str | None = None
    zaiku: str | None = None
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
) -> dict:
    """
    Returns:
        {"method": "gpt_tool" | "regex_fallback", "items": list[dict]}
    """
    client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
    truncated_text = text[:8000]
    user_prompt = f"{JSON_EXTRACT_INSTRUCTIONS}\nOCRテキスト:\n```\n{truncated_text}\n```"

    messages = [
        {
            "role": "system",
            "content": "あなたはOCR後の照明カタログから品番を抽出する日本語テキスト解析エンジンです。",
        },
        {"role": "user", "content": user_prompt},
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "emit_items",
                "description": "抽出した品番候補を配列として返す。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "hinban": {"type": "string"},
                                    "normalized": {"type": "string"},
                                },
                                "required": ["hinban", "normalized"],
                            },
                        }
                    },
                    "required": ["items"],
                },
            },
        }
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
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "emit_items"}},
                messages=messages,
            )

            choice = response.choices[0] if response.choices else None
            tool_calls = getattr(choice.message, "tool_calls", None) if choice else None

            if not tool_calls:
                logger.warning("モデルが関数を呼び出しませんでした。正規表現にフォールバックします。")
                return {"method": "regex_fallback", "items": _fallback_regex_extraction(text)}

            # 取第一個 tool call
            tc = tool_calls[0]
            args_raw = tc.function.arguments or ""
            # 留一手日志，前 400 字符
            logger.debug("tool.arguments (first 400): %s", args_raw[:400].replace("\n", " "))

            args = json.loads(args_raw)
            parsed = args.get("items", [])
            if not isinstance(parsed, list):
                logger.warning("関数引数が配列ではありません。正規表現にフォールバックします。")
                return {"method": "regex_fallback", "items": _fallback_regex_extraction(text)}

            normalized_items = _unique_items(parsed)
            if not normalized_items:
                logger.info("モデルから有効な品番が得られませんでした。正規表現にフォールバックします。")
                return {"method": "regex_fallback", "items": _fallback_regex_extraction(text)}

            return {"method": "gpt_tool", "items": normalized_items}

        except Exception as exc:
            status_code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
            if status_code in (429, 500, 502, 503, 504) and attempt < max_attempts:
                sleep_time = backoff ** attempt
                logger.warning("OpenAI API error (status=%s). Retrying in %.1f seconds...", status_code, sleep_time)
                time.sleep(sleep_time)
                continue
            logger.exception("OpenAI API呼び出しに失敗しました。正規表現にフォールバックします。")
            return {"method": "regex_fallback", "items": _fallback_regex_extraction(text)}

    return {"method": "regex_fallback", "items": _fallback_regex_extraction(text)}


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
        matched_zaiku: str | None = None

        # 完全一致
        row = matcher.hinban_map.get(normalized)
        if row:
            status = "EXACT"
            matched_hinban = row.hinban
            matched_zaiku = row.zaiku or None
            score = 1.0
        else:
            # 子串互含
            for candidate in all_rows:
                if normalized and normalized in candidate.hinban:
                    status = "SUBSTR"
                    matched_hinban = candidate.hinban
                    matched_zaiku = candidate.zaiku or None
                    score = 0.9
                    break
                if candidate.hinban and candidate.hinban in normalized:
                    status = "SUBSTR"
                    matched_hinban = candidate.hinban
                    matched_zaiku = candidate.zaiku or None
                    score = 0.9
                    break

        # 规格关键字回查
        if status == "NONE":
            retry_candidates = matcher.retry(normalized)
            if retry_candidates:
                status = "KIDOU"
                matched_hinban = retry_candidates[0]
                row2 = matcher.hinban_map.get(matched_hinban)
                matched_zaiku = (row2.zaiku if row2 else None)
                score = 0.88

        # 模糊匹配
        if status == "NONE":
            best_ratio = 0.0
            best_row = None
            from difflib import SequenceMatcher
            for candidate in all_rows:
                ratio = SequenceMatcher(None, normalized, candidate.hinban).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_row = candidate
            if best_row and best_ratio >= fuzzy_threshold:
                status = "FUZZY"
                matched_hinban = best_row.hinban
                matched_zaiku = best_row.zaiku or None
                score = round(best_ratio, 3)

        results.append(
            MatchResult(
                input_hinban=hinban,
                normalized=normalized,
                match_status=status,
                score=score,
                matched_hinban=matched_hinban,
                zaiku=matched_zaiku,
            )
        )
    return results


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

    # OCR
    try:
        texts = ocr_pages(str(pdf_file))
    except OCRError as exc:
        message = f"OCR処理に失敗しました: {exc}"
        logger.error(message)
        raise RuntimeError(message) from exc
    except Exception as exc:
        message = f"PDFの読み込みに失敗しました: {exc}"
        logger.error(message)
        raise RuntimeError(message) from exc

    # OCRテキスト結合
    ocr_text = "\n".join(texts)

    # GPT抽出（関数呼び出し方式）
    logger.info("🧠 GPTで品番を抽出中...")
    result = extract_hinbans_with_gpt(
        text=ocr_text,
        model=model,
        base_url=resolved_base_url,
        api_key=resolved_api_key,
        timeout=timeout,
    )
    method = result.get("method", "unknown")
    items = result.get("items", [])

    # 抽出結果の表示 + 保存（method 付き）
    title = "🧠 GPT抽出結果 (Function Call)" if method == "gpt_tool" else "🧪 正規表現抽出（フォールバック）"
    print(f"\n=== {title} ===")
    if not items:
        print("⚠️ 抽出結果が空です。")
    else:
        for i, item in enumerate(items, 1):
            print(f"{i:02d}. {item.get('hinban', '')}  →  {item.get('normalized', '')}")
    print("=" * 60)

    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    gpt_csv_path = logs_dir / f"extract_{method}_{timestamp}.csv"
    pd.DataFrame(items).to_csv(gpt_csv_path, index=False, encoding="utf-8-sig")
    logger.info("💾 抽出結果を保存しました: %s", gpt_csv_path)

    # DB照合
    try:
        matcher = DatabaseMatcher(db_file)
    except ValueError as exc:
        message = str(exc)
        logger.error(message)
        raise RuntimeError(message) from exc

    match_results = _match_semantic_items(items, matcher)

    # 照合結果の表示（在庫付き）
    print("\n=== 🔎 照合結果 ===")
    for result in match_results:
        matched = result.matched_hinban or "-"
        z = result.zaiku or "-"
        print(f"{result.match_status:<6} | {result.input_hinban:<20} -> {matched:<20} | 在庫={z:<10} | score={result.score:0.3f}")

    # DataFrame（在庫列付き）
    df = pd.DataFrame(
        [
            {
                "input_hinban": r.input_hinban,
                "normalized": r.normalized,
                "match_status": r.match_status,
                "score": r.score,
                "matched_hinban": r.matched_hinban,
                "zaiku": r.zaiku,
                "page": r.page,
                "confidence": r.confidence,
                "method": method,
            }
            for r in match_results
        ]
    )

    if save:
        output_path = logs_dir / f"match_{method}_{timestamp}.csv"
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info("💾 照合結果を保存しました: %s", output_path)

    return df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Semantic matcher for hinban extraction")
    parser.add_argument("--pdf", required=True, help="入力PDFのパス")
    parser.add_argument("--db", required=True, help="品番CSVのパス")
    parser.add_argument("--model", default="gpt-4o-mini", help="使用するモデル名")
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
