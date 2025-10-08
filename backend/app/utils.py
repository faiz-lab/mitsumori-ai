import logging
import re
from pathlib import Path
from typing import Iterable, List, Set
import unicodedata

logger = logging.getLogger(__name__)

BLACKLIST = {
    "SCALE",
    "DATE",
    "MM",
    "ISO",
    "PAGE",
    "COPY",
    "SAMPLE",
    "MODEL",
}

TOKEN_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9\-_\/]{3,}")

def ensure_storage_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def normalize_text(value: str) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", value)
    text = text.upper()
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_tokens(text: str) -> List[str]:
    normalized = normalize_text(text)
    candidates: Set[str] = set()
    for match in TOKEN_PATTERN.finditer(normalized):
        token = match.group(0)
        if any(char.isdigit() for char in token) and token not in BLACKLIST:
            candidates.add(token)
    return sorted(candidates)


def write_csv(path: Path, headers: Iterable[str], rows: Iterable[Iterable[str]]) -> None:
    import csv

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


def read_file_bytes(file) -> bytes:
    data = file.read()
    if hasattr(file, "seek"):
        file.seek(0)
    return data


def save_upload_file(upload_file, destination: Path) -> None:
    ensure_storage_dir(destination.parent)
    with destination.open("wb") as buffer:
        buffer.write(read_file_bytes(upload_file.file))


