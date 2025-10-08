from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from pdf2image import convert_from_path
from PIL import Image

logger = logging.getLogger(__name__)


class OCRError(RuntimeError):
    pass


def preprocess_image(image: Image.Image) -> Image.Image:
    import cv2
    import numpy as np

    img_array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    img_array = cv2.medianBlur(img_array, 3)
    img_array = cv2.adaptiveThreshold(
        img_array, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2
    )
    return Image.fromarray(img_array)


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
        text = " ".join(block.text for block in result.blocks)
        texts.append(text)
    return texts


