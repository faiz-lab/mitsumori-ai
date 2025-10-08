from __future__ import annotations

import logging
from typing import List

from pdf2image import convert_from_path
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


class OCRError(RuntimeError):
    """统一抛 OCR 相关错误"""
    pass


# ---------------------------
# 预处理 & 规范化
# ---------------------------
def preprocess_image(image: Image.Image) -> np.ndarray:
    """温和预处理：灰度 + 轻度去噪 + 轻微对比增强（不做二值化，避免细字丢失）"""
    import cv2  # 延迟导入，避免环境没装时影响模块加载
    img = np.array(image)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    # 轻度降噪，保边
    gray = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)
    # 轻微对比拉伸
    gray = cv2.convertScaleAbs(gray, alpha=1.15, beta=0)
    # 还原成3通道，兼容下游
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _normalize_visible_text(s: str) -> str:
    """OCR后统一规范：全角→半角，压空白，转大写"""
    import unicodedata
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = " ".join(s.split())
    return s.upper()


# ---------------------------
# YomiToku 输出兼容适配器
# ---------------------------
def _to_texts_from_result(res) -> List[str]:
    """
    把 YomiToku 的返回结果统一抽成 [page_text, ...]
    兼容：
      - obj.blocks / obj.pages[*].blocks / obj.lines / obj.paragraphs
      - dict: {"pages":[...]} / {"results":[...]} / {"text":"..."}
      - list[dict/obj] / tuple(...)
    """
    def _text_from_block(b):
        for k in ("text", "content", "string"):
            if hasattr(b, k):
                v = getattr(b, k, "")
                if isinstance(v, str):
                    return v
            elif isinstance(b, dict) and isinstance(b.get(k), str):
                return b[k]
        return ""

    def _blocks_from_page(p):
        for attr in ("blocks", "lines", "paragraphs"):
            if hasattr(p, attr):
                xs = getattr(p, attr) or []
                return [x for x in xs if x is not None]
        if isinstance(p, dict):
            for key in ("blocks", "lines", "paragraphs"):
                xs = p.get(key)
                if isinstance(xs, list):
                    return [x for x in xs if x is not None]
        return []

    # tuple：取第一个像结构体的
    if isinstance(res, tuple):
        for item in res:
            if item is None:
                continue
            if isinstance(item, (dict, list)) or any(
                hasattr(item, a) for a in ("blocks", "pages", "lines", "paragraphs")
            ):
                res = item
                break

    # dict
    if isinstance(res, dict):
        if isinstance(res.get("pages"), list):
            texts = []
            for p in res["pages"]:
                blocks = _blocks_from_page(p)
                texts.append(" ".join(filter(None, (_text_from_block(b) for b in blocks))))
            return texts
        if isinstance(res.get("results"), list):
            return [" ".join(filter(None, [
                (r.get("content") if isinstance(r, dict) else getattr(r, "content", "")) or
                (r.get("text")    if isinstance(r, dict) else getattr(r, "text", ""))
                for r in res["results"]
            ]))]
        if isinstance(res.get("text"), str):
            return [res["text"]]
        raise OCRError(f"YomiToku OCR: 未知dict形式: keys={list(res.keys())[:6]}")

    # list
    if isinstance(res, list):
        if not res:
            return [""]
        page_like = any(
            isinstance(x, dict) and any(k in x for k in ("blocks", "lines", "paragraphs", "text", "content"))
            or any(hasattr(x, a) for a in ("blocks", "lines", "paragraphs", "text", "content"))
            for x in res
        )
        if page_like:
            texts = []
            for p in res:
                if isinstance(p, dict) and any(k in p for k in ("text", "content")):
                    texts.append(_text_from_block(p))
                elif any(hasattr(p, a) for a in ("text", "content")):
                    texts.append(_text_from_block(p))
                else:
                    blocks = _blocks_from_page(p)
                    texts.append(" ".join(filter(None, (_text_from_block(b) for b in blocks))))
            return texts
        return [" ".join(filter(None, (_text_from_block(b) for b in res)))]

    # 对象：优先 pages
    if hasattr(res, "pages"):
        pages = getattr(res, "pages") or []
        texts = []
        for p in pages:
            blocks = _blocks_from_page(p)
            texts.append(" ".join(filter(None, (_text_from_block(b) for b in blocks))))
        return texts

    # 次优：blocks/lines/paragraphs
    for attr in ("blocks", "lines", "paragraphs"):
        if hasattr(res, attr):
            blocks = getattr(res, attr) or []
            return [" ".join(filter(None, (_text_from_block(b) for b in blocks)))]

    raise OCRError("YomiTokuのOCR結果の形式を解釈できません（未知の出力）。")


# ---------------------------
# OCR 执行器（YomiToku + Tesseract 兜底）
# ---------------------------
def _run_yomitoku(analyzer, np_img: np.ndarray) -> str:
    result = analyzer(np_img)
    page_texts = _to_texts_from_result(result)
    return _normalize_visible_text(" ".join(t for t in page_texts if t))


def _run_tesseract(np_img: np.ndarray) -> str:
    """兜底：用 tesseract 抓英数字（适合 NNF41030 / XLX460UEN 这种印刷体）"""
    try:
        import cv2
        import pytesseract
    except Exception:
        return ""
    gray = cv2.cvtColor(np_img, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_OTSU | cv2.THRESH_BINARY)
    text = pytesseract.image_to_string(bw, lang="eng+jpn")
    return _normalize_visible_text(text)


def ocr_pages(pdf_path: str, dpi: int = 300) -> List[str]:
    """把 PDF 每页转图识别，返回每页合并后的文本（已做全角转半角和大写）"""
    try:
        from yomitoku import DocumentAnalyzer
    except ImportError as exc:  # pragma: no cover
        raise OCRError(
            "YomiTokuモジュールが見つかりません。ローカルにインストールし、モデルを配置してください。"
        ) from exc

    try:
        images = convert_from_path(pdf_path, dpi=dpi)
    except Exception as exc:  # pragma: no cover
        raise OCRError("pdf2imageがPDFを処理できません。Popplerの導入を確認してください。") from exc

    analyzer = DocumentAnalyzer()
    texts: List[str] = []

    for idx, image in enumerate(images):
        processed = preprocess_image(image)
        raw_np = np.array(image)

        # 1) YomiToku 路线：预处理图 vs 原图，取更长
        try:
            yomi_processed = _run_yomitoku(analyzer, processed)
            yomi_raw = _run_yomitoku(analyzer, raw_np)
        except Exception:  # pragma: no cover
            logger.exception("YomiToku OCR failed on page %d", idx + 1)
            yomi_processed = yomi_raw = ""

        best_yomi = max((yomi_processed, yomi_raw), key=len)

        # 2) 文本太短（<10），再用 tesseract 兜底
        tess = _run_tesseract(processed) if len(best_yomi) < 10 else ""
        final_text = max((best_yomi, tess), key=len)

        # 3) 打样日志
        logger.info("📄 Page %d sample: %r", idx + 1, final_text[:160])

        texts.append(final_text)

    return texts
