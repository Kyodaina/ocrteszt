from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MarketingIntent = Literal[
    "branding",
    "awareness",
    "conversion",
    "product promo",
    "CTA",
    "informational",
    "unclear",
]
ProcessingStage = Literal[
    "queued",
    "loading",
    "preprocessing",
    "OCR running",
    "semantic analysis",
    "completed",
    "failed",
]


class ImageResult(BaseModel):
    id: str
    batch_id: str
    filename: str
    relative_path: str | None = None
    file_hash: str
    duplicate_of: str | None = None
    stage: ProcessingStage
    visible_text: str = ""
    marketing_intent: MarketingIntent = "unclear"
    importance_score: int = Field(default=1, ge=1, le=10)
    confidence_score: int = Field(default=1, ge=1, le=10)
    processing_status: str = "queued"
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempts: int = 0
    thumbnail_url: str | None = None


class BatchSummary(BaseModel):
    batch_id: str
    total_files: int
    completed_files: int
    failed_files: int
    queued_files: int
    estimated_remaining_seconds: int


class LogEntry(BaseModel):
    timestamp: datetime
    level: Literal["INFO", "WARNING", "ERROR"]
    message: str
    context: str | None = None
