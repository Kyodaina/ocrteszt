from __future__ import annotations

import csv
import io
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from backend.main_state import processing_service, state_service

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/snapshot")
async def snapshot() -> dict:
    return state_service.snapshot()


@router.post("/upload")
async def upload(files: list[UploadFile] = File(...)) -> dict:
    payload: list[tuple[str, bytes]] = []
    for file in files:
        content = await file.read()
        payload.append((file.filename or "unnamed", content))
    tasks = await processing_service.enqueue_uploads(payload)
    return {"accepted": len(tasks), "file_ids": [t.file_id for t in tasks]}


@router.post("/process/start")
async def process_start() -> dict:
    await processing_service.start_worker()
    return {"ok": True}


@router.post("/process/retry/{file_id}")
async def process_retry(file_id: str) -> dict:
    ok = await processing_service.retry(file_id)
    if not ok:
        raise HTTPException(status_code=404, detail="file_id not found")
    return {"ok": True}


@router.get("/export/{fmt}")
async def export_results(fmt: str) -> Response:
    rows = [
        {
            "file_id": t.file_id,
            "filename": t.filename,
            "visible_text": t.visible_text,
            "marketing_intent": t.marketing_intent,
            "importance_score": t.importance_score,
            "confidence_score": t.confidence_score,
            "processing_status": t.processing_status,
        }
        for t in state_service.tasks.values()
    ]
    if fmt == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()) if rows else ["file_id"])
        writer.writeheader()
        writer.writerows(rows)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=ocr_results.csv"},
        )
    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        headers = list(rows[0].keys()) if rows else ["file_id"]
        ws.append(headers)
        for row in rows:
            ws.append([row[h] for h in headers])
        binary = io.BytesIO()
        wb.save(binary)
        return Response(
            content=binary.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=ocr_results.xlsx"},
        )
    if fmt == "pdf":
        binary = io.BytesIO()
        c = canvas.Canvas(binary, pagesize=letter)
        y = 750
        c.setFont("Helvetica", 10)
        for row in rows[:150]:
            line = f"{row['filename'][:25]} | {row['marketing_intent']} | imp={row['importance_score']} conf={row['confidence_score']:.2f}"
            c.drawString(40, y, line)
            y -= 14
            if y < 60:
                c.showPage()
                y = 750
        c.save()
        return Response(
            content=binary.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=ocr_results.pdf"},
        )
    raise HTTPException(status_code=400, detail="Unsupported format")
