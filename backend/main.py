from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import db
from .exporters import export_csv, export_pdf, export_xlsx
from .processor import processor, save_upload, sha256_file

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    processor.start()


@app.post("/api/batches")
async def create_batch(
    files: list[UploadFile] = File(...),
    relative_paths: str = Form(default=""),
) -> dict[str, object]:
    batch_id = uuid4().hex
    db.create_batch(batch_id)
    relative_list = [x for x in relative_paths.split("||") if x]
    item_rows = []

    for idx, upload in enumerate(files):
        content = await upload.read()
        stored_path = save_upload(content, upload.filename)
        file_hash = sha256_file(stored_path)
        duplicate_of = None
        existing = db.find_by_hash(file_hash)
        if existing:
            duplicate_of = existing["id"]
        item_rows.append(
            {
                "id": uuid4().hex,
                "batch_id": batch_id,
                "filename": upload.filename,
                "relative_path": relative_list[idx] if idx < len(relative_list) else None,
                "stored_path": str(stored_path),
                "file_hash": file_hash,
                "duplicate_of": duplicate_of,
            }
        )

    db.add_items(item_rows)
    for row in item_rows:
        processor.enqueue(row["id"])
    db.log(batch_id, None, "INFO", f"Batch created with {len(item_rows)} files")
    return {"batch_id": batch_id, "total_files": len(item_rows)}


@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: str) -> dict[str, object]:
    rows = db.get_items_for_batch(batch_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Batch not found")
    completed = sum(1 for r in rows if r["processing_status"] == "completed")
    failed = sum(1 for r in rows if r["processing_status"] == "failed")
    queued = len(rows) - completed - failed
    avg_sec = 12
    eta = math.ceil(queued * avg_sec)
    return {
        "summary": {
            "batch_id": batch_id,
            "total_files": len(rows),
            "completed_files": completed,
            "failed_files": failed,
            "queued_files": queued,
            "estimated_remaining_seconds": eta,
        },
        "items": [
            {
                "id": r["id"],
                "batch_id": r["batch_id"],
                "filename": r["filename"],
                "relative_path": r["relative_path"],
                "file_hash": r["file_hash"],
                "duplicate_of": r["duplicate_of"],
                "stage": r["stage"],
                "visible_text": r["visible_text"],
                "marketing_intent": r["marketing_intent"],
                "importance_score": r["importance_score"],
                "confidence_score": r["confidence_score"],
                "processing_status": r["processing_status"],
                "error_message": r["error_message"],
                "started_at": r["started_at"],
                "finished_at": r["finished_at"],
                "attempts": r["attempts"],
                "thumbnail_url": f"/api/items/{r['id']}/image",
            }
            for r in rows
        ],
        "logs": [dict(x) for x in db.get_logs(batch_id)],
        "now": datetime.utcnow().isoformat(),
    }


@app.get("/api/items/{item_id}/image")
def item_image(item_id: str):
    row = db.get_item(item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return FileResponse(row["stored_path"])


@app.post("/api/items/{item_id}/retry")
def retry_item(item_id: str) -> dict[str, str]:
    row = db.get_item(item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Item not found")
    processor.retry(item_id)
    db.log(row["batch_id"], item_id, "WARNING", "Retry requested")
    return {"status": "queued"}


@app.delete("/api/items/{item_id}")
def delete_item(item_id: str) -> dict[str, str]:
    row = db.get_item(item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Item not found")
    db.update_item(item_id, stage="failed", processing_status="failed", error_message="Deleted by user")
    db.log(row["batch_id"], item_id, "WARNING", "Deleted by user")
    return {"status": "deleted"}


@app.get("/api/batches/{batch_id}/export/{fmt}")
def export(batch_id: str, fmt: str):
    if fmt == "csv":
        path = export_csv(batch_id)
    elif fmt == "xlsx":
        path = export_xlsx(batch_id)
    elif fmt == "pdf":
        path = export_pdf(batch_id)
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")
    return FileResponse(path, filename=path.name)


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
