from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

from .config import settings
from .db import db

HEADERS = [
    "id",
    "filename",
    "relative_path",
    "stage",
    "visible_text",
    "marketing_intent",
    "importance_score",
    "confidence_score",
    "processing_status",
    "error_message",
]


def _rows(batch_id: str) -> list[dict[str, object]]:
    items = db.get_items_for_batch(batch_id)
    return [dict(row) for row in items]


def export_csv(batch_id: str) -> Path:
    out = settings.exports_dir / f"{batch_id}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        for row in _rows(batch_id):
            writer.writerow({key: row.get(key) for key in HEADERS})
    return out


def export_xlsx(batch_id: str) -> Path:
    out = settings.exports_dir / f"{batch_id}.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    ws.append(HEADERS)
    for row in _rows(batch_id):
        ws.append([row.get(key) for key in HEADERS])
    wb.save(out)
    return out


def export_pdf(batch_id: str) -> Path:
    out = settings.exports_dir / f"{batch_id}.pdf"
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    elements = [Paragraph(f"OCR Results - Batch {batch_id}", styles["Heading2"]), Spacer(1, 12)]
    data = [HEADERS]
    for row in _rows(batch_id):
        data.append([
            str(row.get("id", ""))[:10],
            str(row.get("filename", ""))[:40],
            str(row.get("relative_path", ""))[:30],
            str(row.get("stage", "")),
            str(row.get("marketing_intent", "")),
            str(row.get("importance_score", "")),
            str(row.get("confidence_score", "")),
            str(row.get("processing_status", "")),
        ])
    elements.append(Table(data, repeatRows=1))
    doc.build(elements)
    return out
