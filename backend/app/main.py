from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from openpyxl import Workbook

from .model_service import QwenOCRService
from .schemas import FileTask, LogEvent
from .state import AppState

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "output"
UPLOADS_DIR = OUTPUT_DIR / "uploads"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Local OCR Analyzer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

state = AppState(OUTPUT_DIR)
model_service = QwenOCRService(BASE_DIR / "models")
clients: set[WebSocket] = set()


async def broadcast(message: dict[str, Any]) -> None:
    stale: list[WebSocket] = []
    for ws in clients:
        try:
            await ws.send_json(message)
        except Exception:
            stale.append(ws)
    for ws in stale:
        clients.discard(ws)


async def push_log(level: str, msg: str, task_id: str | None = None, stack: str | None = None) -> None:
    evt = LogEvent(timestamp=datetime.utcnow(), level=level, message=msg, task_id=task_id, stack_trace=stack)
    state.add_log(evt)
    await broadcast({"type": "log", "payload": evt.model_dump(mode="json")})


async def publish_task(task: FileTask) -> None:
    await broadcast({"type": "task", "payload": task.model_dump(mode="json")})


async def publish_stats() -> None:
    await broadcast({"type": "stats", "payload": state.stats().model_dump(mode="json")})


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def process_task(task_id: str) -> None:
    task = state.tasks[task_id]
    started = datetime.utcnow()
    task.stage = "loading"
    task.started_at = started
    task.updated_at = started
    await publish_task(task)
    await publish_stats()

    try:
        task.stage = "preprocessing"
        task.updated_at = datetime.utcnow()
        await publish_task(task)

        img_path = Path(task.file_path)
        if not img_path.exists():
            raise FileNotFoundError("Uploaded file missing")

        task.stage = "OCR running"
        task.updated_at = datetime.utcnow()
        await publish_task(task)

        async def run_inference() -> Any:
            return await asyncio.to_thread(model_service.run, img_path)

        result = await asyncio.wait_for(run_inference(), timeout=state.timeout_seconds)

        task.stage = "semantic analysis"
        task.updated_at = datetime.utcnow()
        await publish_task(task)

        task.result = result
        task.stage = "completed"
        task.finished_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        await publish_task(task)
        await push_log("info", f"Completed {task.filename}", task.id)
    except asyncio.TimeoutError:
        warning = f"Task timed out after {state.timeout_seconds}s"
        await push_log("warning", warning, task.id)
        if task.retries < state.max_retries:
            task.retries += 1
            task.stage = "queued"
            task.error = warning
            task.updated_at = datetime.utcnow()
            await state.queue.put(task.id)
            await push_log("warning", f"Retrying {task.filename} (attempt {task.retries})", task.id)
        else:
            task.stage = "failed"
            task.error = warning
            task.updated_at = datetime.utcnow()
            task.finished_at = datetime.utcnow()
            await publish_task(task)
    except Exception as exc:
        stack = traceback.format_exc()
        task.stage = "failed"
        task.error = str(exc)
        task.updated_at = datetime.utcnow()
        task.finished_at = datetime.utcnow()
        await publish_task(task)
        await push_log("error", f"Failed {task.filename}: {exc}", task.id, stack)

    if task.finished_at:
        dur = max((task.finished_at - started).total_seconds(), 0.1)
        state.avg_duration_seconds = (state.avg_duration_seconds * 0.8) + (dur * 0.2)
    await publish_stats()
    state.persist()


async def worker() -> None:
    await push_log("info", "Worker started")
    rt = await asyncio.to_thread(model_service.load)
    state.model_status = {"loaded": True, "device": rt.device, "model_id": rt.model_id}
    await broadcast({"type": "model", "payload": state.model_status})
    await push_log("info", f"Model loaded: {rt.model_id} on {rt.device}")

    while True:
        task_id = await state.queue.get()
        if task_id in state.tasks:
            await process_task(task_id)
        state.queue.task_done()


@app.on_event("startup")
async def startup_event() -> None:
    state.load()
    pending = state.mark_resume_pending()
    for tid in pending:
        await state.queue.put(tid)
    asyncio.create_task(worker())


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "model": state.model_status, "stats": state.stats().model_dump()}


@app.post("/api/queue")
async def queue_files(files: list[UploadFile] = File(...)) -> JSONResponse:
    enqueued = []
    for f in files:
        content = await f.read()
        digest = _sha256(content)
        existing = next((t for t in state.tasks.values() if t.sha256 == digest), None)
        file_id = str(uuid.uuid4())
        target = UPLOADS_DIR / f"{file_id}_{f.filename}"
        target.write_bytes(content)
        now = datetime.utcnow()
        task = FileTask(
            id=file_id,
            filename=f.filename,
            file_path=str(target),
            sha256=digest,
            duplicate_of=existing.id if existing else None,
            size_bytes=len(content),
            created_at=now,
            updated_at=now,
        )
        state.tasks[file_id] = task
        await publish_task(task)
        if existing:
            task.stage = "completed"
            task.result = existing.result
            task.updated_at = datetime.utcnow()
            task.finished_at = datetime.utcnow()
            await push_log("info", f"Duplicate detected: {task.filename}", task.id)
        else:
            await state.queue.put(file_id)
        enqueued.append(file_id)
    await publish_stats()
    state.persist()
    return JSONResponse({"enqueued": enqueued})


@app.get("/api/tasks")
async def get_tasks() -> dict[str, Any]:
    return {
        "tasks": [t.model_dump(mode="json") for t in state.tasks.values()],
        "stats": state.stats().model_dump(mode="json"),
        "logs": [x.model_dump(mode="json") for x in state.logs],
        "model": state.model_status,
    }


@app.post("/api/retry/{task_id}")
async def retry_task(task_id: str) -> JSONResponse:
    task = state.tasks.get(task_id)
    if not task:
        return JSONResponse({"error": "Not found"}, status_code=404)
    task.stage = "queued"
    task.error = None
    task.updated_at = datetime.utcnow()
    await state.queue.put(task_id)
    await publish_task(task)
    await publish_stats()
    return JSONResponse({"status": "queued"})


@app.get("/api/export/{fmt}")
async def export_results(fmt: str):
    rows = []
    for t in state.tasks.values():
        res = t.result.model_dump() if t.result else {}
        rows.append(
            {
                "id": t.id,
                "filename": t.filename,
                "status": t.stage,
                "visible_text": res.get("visible_text", ""),
                "marketing_intent": res.get("marketing_intent", "unclear"),
                "importance_score": res.get("importance_score", ""),
                "confidence_score": res.get("confidence_score", ""),
                "duplicate_of": t.duplicate_of or "",
                "error": t.error or "",
            }
        )

    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if fmt == "json":
        path = OUTPUT_DIR / f"results_{stamp}.json"
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        return FileResponse(path)

    if fmt == "csv":
        path = OUTPUT_DIR / f"results_{stamp}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["id"])
            writer.writeheader()
            writer.writerows(rows)
        return FileResponse(path)

    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "OCR Results"
        headers = list(rows[0].keys()) if rows else ["id"]
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h, "") for h in headers])
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=results_{stamp}.xlsx"},
        )

    return JSONResponse({"error": "Unsupported format"}, status_code=400)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    clients.add(websocket)
    await websocket.send_json(
        {
            "type": "snapshot",
            "payload": {
                "tasks": [t.model_dump(mode="json") for t in state.tasks.values()],
                "stats": state.stats().model_dump(mode="json"),
                "logs": [x.model_dump(mode="json") for x in state.logs],
                "model": state.model_status,
            },
        }
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.discard(websocket)
