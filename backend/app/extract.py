from __future__ import annotations

import logging
from pathlib import Path
from typing import List
from pprint import pprint
import pdfplumber

from .ocr_backend import ocr_pages, OCRError

logger = logging.getLogger(__name__)


def extract_text_pages(pdf_path: Path) -> List[str]:
    texts: List[str] = []
    fallback_needed = False
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if len(text.strip()) < 20:
                fallback_needed = True
            texts.append(text)
    if fallback_needed or all(len(t.strip()) < 20 for t in texts):
        logger.info("Falling back to OCR for %s", pdf_path.name)
        try:
            texts = ocr_pages(str(pdf_path))
            pprint(texts)
        except OCRError:
            raise
        except Exception as exc:  # pragma: no cover
            logger.exception("Unexpected OCR failure")
            raise OCRError("OCRの初期化に失敗しました。ログを確認してください。") from exc
    return texts
