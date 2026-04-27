from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal, Optional


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


class OCRResult(BaseModel):
    visible_text: str = ""
    marketing_intent: MarketingIntent = "unclear"
    importance_score: int = Field(default=1, ge=1, le=10)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    processing_status: ProcessingStage = "queued"


class FileTask(BaseModel):
    id: str
    filename: str
    file_path: str
    sha256: str
    duplicate_of: Optional[str] = None
    size_bytes: int = 0
    created_at: datetime
    updated_at: datetime
    stage: ProcessingStage = "queued"
    retries: int = 0
    error: Optional[str] = None
    result: Optional[OCRResult] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class GlobalStats(BaseModel):
    total_files: int = 0
    completed_files: int = 0
    failed_files: int = 0
    queued_files: int = 0
    estimated_remaining_seconds: Optional[float] = None


class LogEvent(BaseModel):
    timestamp: datetime
    level: Literal["info", "warning", "error"]
    message: str
    task_id: Optional[str] = None
    stack_trace: Optional[str] = None


class WSMessage(BaseModel):
    type: Literal["task", "stats", "log", "snapshot", "model"]
    payload: dict
