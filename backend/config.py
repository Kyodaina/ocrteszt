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
    max_image_side: int = 1280
    max_pixels: int = 1280 * 1280
    max_new_tokens: int = 256
    low_memory_max_new_tokens: int = 96
    output_dir: Path = Path("output")
    uploads_dir: Path = Path("output/uploads")
    exports_dir: Path = Path("output/exports")
    db_path: Path = Path("output/app.db")


settings = Settings()
