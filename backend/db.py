from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import settings


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS batches (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    relative_path TEXT,
                    stored_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    duplicate_of TEXT,
                    stage TEXT NOT NULL,
                    visible_text TEXT NOT NULL DEFAULT '',
                    marketing_intent TEXT NOT NULL DEFAULT 'unclear',
                    importance_score INTEGER NOT NULL DEFAULT 1,
                    confidence_score INTEGER NOT NULL DEFAULT 1,
                    processing_status TEXT NOT NULL DEFAULT 'queued',
                    error_message TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(batch_id) REFERENCES batches(id)
                );
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT,
                    item_id TEXT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    context TEXT,
                    timestamp TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_items_batch ON items(batch_id);
                CREATE INDEX IF NOT EXISTS idx_logs_batch ON logs(batch_id);
                CREATE INDEX IF NOT EXISTS idx_items_hash ON items(file_hash);
                """
            )

    def create_batch(self, batch_id: str) -> None:
        with self.connection() as conn:
            conn.execute("INSERT INTO batches(id, created_at) VALUES (?, ?)", (batch_id, _utc_now()))

    def add_items(self, rows: Iterable[dict[str, Any]]) -> None:
        with self.connection() as conn:
            conn.executemany(
                """
                INSERT INTO items (
                    id, batch_id, filename, relative_path, stored_path, file_hash, duplicate_of,
                    stage, processing_status, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', 'queued', ?)
                """,
                [
                    (
                        row["id"],
                        row["batch_id"],
                        row["filename"],
                        row.get("relative_path"),
                        row["stored_path"],
                        row["file_hash"],
                        row.get("duplicate_of"),
                        json.dumps(row.get("metadata", {})),
                    )
                    for row in rows
                ],
            )

    def log(self, batch_id: str | None, item_id: str | None, level: str, message: str, context: str | None = None) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO logs(batch_id, item_id, level, message, context, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (batch_id, item_id, level, message, context, _utc_now()),
            )

    def update_item(self, item_id: str, **fields: Any) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [item_id]
        with self.connection() as conn:
            conn.execute(f"UPDATE items SET {assignments} WHERE id = ?", values)

    def get_items_for_batch(self, batch_id: str) -> list[sqlite3.Row]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM items WHERE batch_id = ? ORDER BY filename", (batch_id,)).fetchall()
        return rows

    def get_item(self, item_id: str) -> sqlite3.Row | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return row

    def get_logs(self, batch_id: str, limit: int = 300) -> list[sqlite3.Row]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM logs WHERE batch_id = ? ORDER BY id DESC LIMIT ?", (batch_id, limit)
            ).fetchall()
        return list(reversed(rows))

    def find_by_hash(self, file_hash: str) -> sqlite3.Row | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT id, batch_id FROM items WHERE file_hash = ? AND processing_status = 'completed' LIMIT 1",
                (file_hash,),
            ).fetchone()
        return row

    def list_pending_items(self) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute(
                "SELECT * FROM items WHERE processing_status IN ('queued', 'loading', 'preprocessing', 'OCR running', 'semantic analysis') ORDER BY rowid"
            ).fetchall()


db = Database(settings.db_path)
