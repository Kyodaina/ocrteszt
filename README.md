# Local-First Bulk OCR + Semantic Analysis

Production-ready local web app for large-batch image OCR and semantic interpretation using **Qwen 2.5 VL only**.

## Features
- Drag/drop files and folder uploads
- Queue for 1000+ images
- Per-file statuses: queued/loading/preprocessing/OCR running/semantic analysis/completed/failed
- Live WebSocket progress + logs (warnings, retries, stack traces)
- Timeout protection + retry
- Duplicate detection by SHA256
- Resume interrupted batch from saved state
- Export JSON / CSV / XLSX
- Search + sort table by importance/confidence
- Responsive black/white premium UI with animations
- Auto GPU usage (CUDA) fallback to CPU

## Project Structure
- `backend/` FastAPI + worker + Qwen runtime
- `frontend/` React + Vite + Tailwind + Framer Motion
- `models/` local HuggingFace cache
- `output/` uploads/results/session state
- `start.py` one-command bootstrap and launch
- `requirements.txt` backend dependencies

## Run
```bash
python start.py
```

`start.py` will:
1. create `.venv` if missing
2. install Python deps
3. install frontend deps
4. download Qwen model if missing
5. start backend/frontend
6. wait until both are ready
7. open browser automatically
8. print diagnostics

## API quick reference
- `POST /api/queue` multipart `files`
- `GET /api/tasks`
- `POST /api/retry/{task_id}`
- `GET /api/export/{json|csv|xlsx}`
- `GET /api/health`
- `WS /ws`
