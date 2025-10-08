import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.utils import extract_tokens, normalize_text


def test_normalize_and_extract():
    text = "ｍｎ−450x test SCALE ZX_9900"
    normalized = normalize_text(text)
    assert "MN-450X" in normalized
    tokens = extract_tokens(text)
    assert "MN-450X" in tokens
    assert "ZX_9900" in tokens
    assert "SCALE" not in tokens
