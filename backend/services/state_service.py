from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.config import STATE_FILE
from backend.schemas import GlobalProgress, ImageTask


class StateService:
    def __init__(self, state_path: Path = STATE_FILE) -> None:
        self.state_path = state_path
        self.tasks: dict[str, ImageTask] = {}

    def load(self) -> None:
        if not self.state_path.exists():
            return
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        tasks = data.get("tasks", {})
        self.tasks = {k: ImageTask(**v) for k, v in tasks.items()}

    def save(self) -> None:
        payload = {
            "updated_at": datetime.utcnow().isoformat(),
            "tasks": {k: v.model_dump(mode="json") for k, v in self.tasks.items()},
        }
        self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def progress(self) -> GlobalProgress:
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks.values() if t.status == "completed")
        failed = sum(1 for t in self.tasks.values() if t.status == "failed")
        active = max(total - completed - failed, 0)
        eta = active * 15
        return GlobalProgress(
            total_files=total,
            completed_files=completed,
            failed_files=failed,
            estimated_remaining_seconds=eta,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "tasks": [t.model_dump(mode="json") for t in self.tasks.values()],
            "global": self.progress().model_dump(),
        }
