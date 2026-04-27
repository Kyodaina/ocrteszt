from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Stage = Literal[
    "queued",
    "loading",
    "preprocessing",
    "ocr_running",
    "semantic_analysis",
    "completed",
    "failed",
]

MarketingIntent = Literal[
    "branding",
    "awareness",
    "conversion",
    "product promo",
    "CTA",
    "informational",
    "unclear",
]


class ImageTask(BaseModel):
    file_id: str
    filename: str
    path: str
    size: int
    sha256: str
    status: Stage = "queued"
    processing_status: str = "queued"
    visible_text: str = ""
    marketing_intent: MarketingIntent = "unclear"
    importance_score: int = 1
    confidence_score: float = 0.0
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class LogEvent(BaseModel):
    ts: datetime = Field(default_factory=datetime.utcnow)
    level: Literal["info", "warning", "error"]
    message: str
    file_id: str | None = None
    trace: str | None = None


class GlobalProgress(BaseModel):
    total_files: int = 0
    completed_files: int = 0
    failed_files: int = 0
    estimated_remaining_seconds: int = 0


class WsEvent(BaseModel):
    kind: Literal["file_update", "global", "log", "snapshot"]
    payload: dict
