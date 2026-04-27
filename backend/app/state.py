from __future__ import annotations

import asyncio
import json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Deque

from .schemas import FileTask, GlobalStats, LogEvent


class AppState:
    def __init__(self, output_dir: Path) -> None:
        self.tasks: dict[str, FileTask] = {}
        self.logs: Deque[LogEvent] = deque(maxlen=2000)
        self.output_dir = output_dir
        self.state_file = output_dir / "session_state.json"
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.timeout_seconds = 120
        self.max_retries = 1
        self.avg_duration_seconds = 8.0
        self.model_status = {"loaded": False, "device": "cpu", "model_id": ""}

    def add_log(self, event: LogEvent) -> None:
        self.logs.append(event)

    def stats(self) -> GlobalStats:
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks.values() if t.stage == "completed")
        failed = sum(1 for t in self.tasks.values() if t.stage == "failed")
        queued = sum(1 for t in self.tasks.values() if t.stage in {"queued", "loading", "preprocessing", "OCR running", "semantic analysis"})
        est = queued * self.avg_duration_seconds if queued else 0
        return GlobalStats(
            total_files=total,
            completed_files=completed,
            failed_files=failed,
            queued_files=queued,
            estimated_remaining_seconds=est,
        )

    def persist(self) -> None:
        payload = {
            "tasks": {k: v.model_dump(mode="json") for k, v in self.tasks.items()},
            "logs": [x.model_dump(mode="json") for x in list(self.logs)[-200:]],
            "model_status": self.model_status,
        }
        self.state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> None:
        if not self.state_file.exists():
            return
        raw = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.tasks = {k: FileTask.model_validate(v) for k, v in raw.get("tasks", {}).items()}
        self.logs = deque((LogEvent.model_validate(x) for x in raw.get("logs", [])), maxlen=2000)
        self.model_status.update(raw.get("model_status", {}))

    def mark_resume_pending(self) -> list[str]:
        pending_ids: list[str] = []
        for tid, task in self.tasks.items():
            if task.stage not in {"completed", "failed"}:
                task.stage = "queued"
                task.error = "Recovered from previous interrupted run"
                task.updated_at = datetime.utcnow()
                pending_ids.append(tid)
        return pending_ids
