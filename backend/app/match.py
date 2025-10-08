from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd

from .utils import extract_tokens, normalize_text

logger = logging.getLogger(__name__)


@dataclass
class MatchRow:
    hinban: str
    kidou: str
    zaiku: str | None = None


class DatabaseMatcher:
    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path
        self.hinban_map: Dict[str, MatchRow] = {}
        self.kidou_map: Dict[str, List[MatchRow]] = {}
        self._load()

    def _load(self) -> None:
        df = pd.read_csv(self.csv_path)
        if "hinban" not in df.columns or "kidou" not in df.columns:
            raise ValueError("CSVに 'hinban' と 'kidou' 列が必要です。ファイルを確認してください。")
        zaiku_exists = "zaiku" in df.columns
        for _, row in df.iterrows():
            hinban = normalize_text(str(row.get("hinban", "")))
            kidou = normalize_text(str(row.get("kidou", "")))
            zaiku = str(row.get("zaiku")) if zaiku_exists else None
            match_row = MatchRow(hinban=hinban, kidou=kidou, zaiku=zaiku)
            if hinban:
                self.hinban_map[hinban] = match_row
            for token in extract_tokens(kidou):
                self.kidou_map.setdefault(token, []).append(match_row)

    def match_token(self, token: str) -> tuple[List[MatchRow], List[MatchRow]]:
        hinban_matches: List[MatchRow] = []
        kidou_matches: List[MatchRow] = []
        normalized = normalize_text(token)
        row = self.hinban_map.get(normalized)
        if row:
            hinban_matches.append(row)
        kidou_matches = self.kidou_map.get(normalized, [])
        return hinban_matches, kidou_matches

    def retry(self, token: str) -> List[str]:
        normalized = normalize_text(token)
        candidates = []
        if normalized in self.hinban_map:
            candidates.append(self.hinban_map[normalized].hinban)
        candidates.extend({row.hinban for row in self.kidou_map.get(normalized, [])})
        return sorted(set(candidates))


