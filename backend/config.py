from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Local-First OCR Studio"
    model_id: str = "Qwen/Qwen2.5-VL-3B-Instruct"
    host: str = "127.0.0.1"
    port: int = 8000
    processing_timeout_seconds: int = 180
    max_workers: int = 1
    prefer_cpu: bool = True
    output_dir: Path = Path("output")
    uploads_dir: Path = Path("output/uploads")
    exports_dir: Path = Path("output/exports")
    db_path: Path = Path("output/app.db")


settings = Settings()
