from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from pdf2image import convert_from_path
from PIL import Image

import numpy as np

logger = logging.getLogger(__name__)


class OCRError(RuntimeError):
    pass


def preprocess_image(image: Image.Image) -> np.ndarray:
    import cv2

    img_array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    img_array = cv2.medianBlur(img_array, 3)
    img_array = cv2.adaptiveThreshold(
        img_array, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2
    )
    return cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)


def ocr_pages(pdf_path: str, dpi: int = 350) -> List[str]:
    try:
        from yomitoku import DocumentAnalyzer
    except ImportError as exc:  # pragma: no cover
        raise OCRError(
            "YomiTokuモジュールが見つかりません。ローカルにインストール済みか確認し、"
            "オンラインAPIに依存しないよう事前にモデルファイルを配置してください。"
        ) from exc

    try:
        images = convert_from_path(pdf_path, dpi=dpi)
    except Exception as exc:  # pragma: no cover
        raise OCRError(
            "pdf2imageがPDFを処理できません。Popplerがインストールされているか確認してください。"
        ) from exc

    analyzer = DocumentAnalyzer()
    texts: List[str] = []
    for image in images:
        processed = preprocess_image(image)
        try:
            result = analyzer(processed)
        except Exception as exc:  # pragma: no cover
            logger.exception("YomiToku OCR failed")
            raise OCRError(
                "OCR処理に失敗しました。YomiTokuのローカルモデル配置と権限を確認してください。"
            ) from exc

        if isinstance(result, tuple):
            result_candidates = [item for item in result if item is not None]
            result_obj = next(
                (
                    item
                    for item in result_candidates
                    if hasattr(item, "blocks") or hasattr(item, "pages")
                ),
                result_candidates[0] if result_candidates else result,
            )
        else:
            result_obj = result

        if hasattr(result_obj, "blocks"):
            blocks = result_obj.blocks
        elif hasattr(result_obj, "pages"):
            blocks = [block for page in result_obj.pages for block in getattr(page, "blocks", [])]
        else:
            raise OCRError(
                "YomiTokuのOCR結果の形式を解釈できません。ライブラリのバージョンを確認してください。"
            )

        text = " ".join(getattr(block, "text", "") for block in blocks if getattr(block, "text", ""))
        texts.append(text)
    return texts


