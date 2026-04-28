# Local-First OCR Studio (Qwen 2.5 VL)

Production-ready local-first web application for bulk image OCR + semantic analysis using **Qwen 2.5 VL** only.

## Features

- Drag & drop single images, multiple images, and folders.
- Batch processing queue with per-file lifecycle states:
  - queued
  - loading
  - preprocessing
  - OCR running
  - semantic analysis
  - completed
  - failed
- Global progress panel:
  - total/completed/failed
  - ETA
- Live log panel with timestamps, warnings, retries, and stack traces.
- Timeout protection + retry + delete per file.
- Duplicate image detection via SHA-256.
- Resume pending queue items after restart.
- Exports: CSV, XLSX, PDF.
- Searchable and sortable results.
- Local inference only (no cloud APIs).
- Model loaded once, reused for all files.
- Windows-friendly startup and local filesystem paths.

## Project Structure

```
/app
/backend
/frontend
/models
/output
/start.py
/requirements.txt
/README.md
```

## Install

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python start.py
```

Open: `http://127.0.0.1:8000`

## Model Notes

- Default model: `Qwen/Qwen2.5-VL-3B-Instruct`.
- Runs on CPU by default (for broader compatibility).
- To allow GPU, set `prefer_cpu=False` in `backend/config.py`.

## API Endpoints

- `POST /api/batches` upload files + optional folder relative paths.
- `GET /api/batches/{batch_id}` get global progress, per-file results, logs.
- `POST /api/items/{item_id}/retry` retry failed/hung item.
- `DELETE /api/items/{item_id}` mark item as removed.
- `GET /api/batches/{batch_id}/export/csv|xlsx|pdf` export results.

## Important Runtime Behavior

- Images are stored under `output/uploads`.
- Results/log state stored in SQLite `output/app.db`.
- Pending items are resumed on startup.
- If processing exceeds timeout (`backend/config.py`), item is marked failed with warning.

## Output Schema Per Image

- `visible_text`
- `marketing_intent` (`branding`, `awareness`, `conversion`, `product promo`, `CTA`, `informational`, `unclear`)
- `importance_score` (1-10)
- `confidence_score` (1-10)
- `processing_status`

