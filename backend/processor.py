from __future__ import annotations

import hashlib
import queue
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image

from .config import settings
from .db import db
from .model_service import qwen_service


@dataclass
class QueueItem:
    item_id: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BatchProcessor:
    def __init__(self) -> None:
        self.queue: queue.Queue[QueueItem] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._executor = ThreadPoolExecutor(max_workers=settings.max_workers)
        self._active = False

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._thread.start()
        self._resume_pending()

    def _resume_pending(self) -> None:
        pending = db.list_pending_items()
        for row in pending:
            self.queue.put(QueueItem(item_id=row["id"]))
            db.log(row["batch_id"], row["id"], "WARNING", "Resumed pending item after restart")

    def enqueue(self, item_id: str) -> None:
        self.queue.put(QueueItem(item_id=item_id))

    def retry(self, item_id: str) -> None:
        db.update_item(item_id, stage="queued", processing_status="queued", error_message=None)
        self.enqueue(item_id)

    def _run(self) -> None:
        while True:
            queue_item = self.queue.get()
            row = db.get_item(queue_item.item_id)
            if row is None:
                continue
            batch_id = row["batch_id"]
            if row["duplicate_of"]:
                db.update_item(
                    row["id"],
                    stage="completed",
                    processing_status="completed",
                    visible_text="",
                    marketing_intent="informational",
                    importance_score=1,
                    confidence_score=10,
                    finished_at=now_iso(),
                    error_message=None,
                )
                db.log(batch_id, row["id"], "INFO", f"Duplicate detected: {row['duplicate_of']}")
                continue

            db.update_item(row["id"], stage="loading", processing_status="loading", started_at=now_iso())
            db.log(batch_id, row["id"], "INFO", "Loading image")
            db.update_item(row["id"], attempts=row["attempts"] + 1)
            future = self._executor.submit(self._process_item, row["id"], Path(row["stored_path"]))
            try:
                result = future.result(timeout=settings.processing_timeout_seconds)
                db.update_item(
                    row["id"],
                    stage="completed",
                    processing_status="completed",
                    visible_text=result["visible_text"],
                    marketing_intent=result["marketing_intent"],
                    importance_score=result["importance_score"],
                    confidence_score=result["confidence_score"],
                    error_message=None,
                    finished_at=now_iso(),
                )
                db.log(batch_id, row["id"], "INFO", "Completed")
            except FutureTimeout:
                db.update_item(
                    row["id"],
                    stage="failed",
                    processing_status="failed",
                    error_message=f"Timed out after {settings.processing_timeout_seconds}s",
                    finished_at=now_iso(),
                )
                db.log(batch_id, row["id"], "WARNING", "Timeout during processing")
            except Exception as exc:  # noqa: BLE001
                trace = traceback.format_exc(limit=8)
                db.update_item(
                    row["id"],
                    stage="failed",
                    processing_status="failed",
                    error_message=str(exc),
                    finished_at=now_iso(),
                )
                db.log(batch_id, row["id"], "ERROR", str(exc), context=trace)

    def _process_item(self, item_id: str, image_path: Path) -> dict[str, object]:
        row = db.get_item(item_id)
        if row is None:
            raise ValueError("Missing item")
        db.update_item(item_id, stage="preprocessing", processing_status="preprocessing")
        db.log(row["batch_id"], item_id, "INFO", "Preprocessing")
        self._verify_image(image_path)
        db.update_item(item_id, stage="OCR running", processing_status="OCR running")
        db.log(row["batch_id"], item_id, "INFO", "OCR running with Qwen 2.5 VL")
        model_output = qwen_service.analyze_image(image_path)
        db.update_item(item_id, stage="semantic analysis", processing_status="semantic analysis")
        db.log(row["batch_id"], item_id, "INFO", "Semantic analysis completed")
        return {
            "visible_text": model_output.visible_text,
            "marketing_intent": model_output.marketing_intent,
            "importance_score": model_output.importance_score,
            "confidence_score": model_output.confidence_score,
        }

    @staticmethod
    def _verify_image(path: Path) -> None:
        with Image.open(path) as image:
            image.verify()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_upload(content: bytes, filename: str) -> Path:
    ext = Path(filename).suffix.lower()
    target = settings.uploads_dir / f"{uuid4().hex}{ext}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


processor = BatchProcessor()
