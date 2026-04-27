from __future__ import annotations

import asyncio
import hashlib
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable

from backend.config import DEFAULT_TIMEOUT_SECONDS, UPLOAD_DIR
from backend.schemas import ImageTask
from backend.services.model_service import QwenVlService
from backend.services.state_service import StateService
from backend.services.ws_service import WsHub


class ProcessingService:
    def __init__(self, state: StateService, ws: WsHub) -> None:
        self.state = state
        self.ws = ws
        self.model = QwenVlService()
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.running = False
        self.timeout_seconds = DEFAULT_TIMEOUT_SECONDS

    async def enqueue_uploads(self, files: Iterable[tuple[str, bytes]]) -> list[ImageTask]:
        created: list[ImageTask] = []
        for filename, content in files:
            sha = hashlib.sha256(content).hexdigest()
            duplicate = next((t for t in self.state.tasks.values() if t.sha256 == sha), None)
            if duplicate:
                created.append(duplicate)
                await self.ws.broadcast("log", {"level": "warning", "message": f"Duplicate skipped: {filename}", "file_id": duplicate.file_id})
                continue
            file_id = str(uuid.uuid4())
            out_path = UPLOAD_DIR / f"{file_id}_{Path(filename).name}"
            out_path.write_bytes(content)
            task = ImageTask(file_id=file_id, filename=filename, path=str(out_path), size=len(content), sha256=sha)
            self.state.tasks[file_id] = task
            await self.queue.put(file_id)
            created.append(task)
            await self.ws.broadcast("file_update", task.model_dump(mode="json"))
        self.state.save()
        await self.ws.broadcast("global", self.state.progress().model_dump())
        return created

    async def start_worker(self) -> None:
        if self.running:
            return
        self.running = True
        asyncio.create_task(self._worker_loop())

    async def _worker_loop(self) -> None:
        await self.ws.broadcast("log", {"level": "info", "message": "Worker started"})
        while self.running:
            file_id = await self.queue.get()
            task = self.state.tasks.get(file_id)
            if task is None:
                continue
            try:
                await self._process_task(task)
            except Exception:
                task.status = "failed"
                task.processing_status = "failed"
                task.error = traceback.format_exc(limit=3)
                await self.ws.broadcast("log", {"level": "error", "message": "Task failed", "file_id": task.file_id, "trace": task.error})
                await self.ws.broadcast("file_update", task.model_dump(mode="json"))
            self.state.save()
            await self.ws.broadcast("global", self.state.progress().model_dump())
            self.queue.task_done()

    async def _process_task(self, task: ImageTask) -> None:
        task.started_at = datetime.utcnow()
        await self._set_stage(task, "loading")
        await asyncio.sleep(0.05)
        await self._set_stage(task, "preprocessing")
        await asyncio.sleep(0.05)
        await self._set_stage(task, "ocr_running")
        path = Path(task.path)

        try:
            output = await asyncio.wait_for(asyncio.to_thread(self.model.analyze_image, path), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            task.status = "failed"
            task.processing_status = "timeout"
            task.error = f"Timed out after {self.timeout_seconds}s"
            await self.ws.broadcast("log", {"level": "warning", "message": task.error, "file_id": task.file_id})
            await self.ws.broadcast("file_update", task.model_dump(mode="json"))
            return

        await self._set_stage(task, "semantic_analysis")
        task.visible_text = output.get("visible_text", "")
        task.marketing_intent = output.get("marketing_intent", "unclear")
        task.importance_score = int(output.get("importance_score", 1))
        task.confidence_score = float(output.get("confidence_score", 0.0))
        task.completed_at = datetime.utcnow()
        task.status = "completed"
        task.processing_status = "completed"
        await self.ws.broadcast("file_update", task.model_dump(mode="json"))

    async def _set_stage(self, task: ImageTask, stage: str) -> None:
        task.status = stage  # type: ignore[assignment]
        task.processing_status = stage
        await self.ws.broadcast("file_update", task.model_dump(mode="json"))

    async def retry(self, file_id: str) -> bool:
        task = self.state.tasks.get(file_id)
        if not task:
            return False
        task.error = None
        task.status = "queued"
        task.processing_status = "queued"
        await self.queue.put(file_id)
        self.state.save()
        await self.ws.broadcast("file_update", task.model_dump(mode="json"))
        return True
