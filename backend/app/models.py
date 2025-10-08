from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    task_id: str


class StatusTotals(BaseModel):
    tokens: int = 0
    hit_hinban: int = 0
    hit_spec: int = 0
    fail: int = 0


class StatusResponse(BaseModel):
    progress: int
    totals: StatusTotals
    pages: int


class ResultRow(BaseModel):
    pdf_name: str
    page: int
    token: str
    matched_type: str
    matched_hinban: str
    zaiko: Optional[str] = None


class FailureRow(BaseModel):
    pdf_name: str
    page: int
    token: str


class ResultsResponse(BaseModel):
    rows: List[ResultRow]
    download_url: str


class FailuresResponse(BaseModel):
    rows: List[FailureRow]
    download_url: str


class RetryRequest(BaseModel):
    task_id: str
    token: str


class RetryResponse(BaseModel):
    candidates: List[str]


