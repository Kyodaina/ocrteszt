# Local-First Bulk OCR + Semantic Analyzer (Qwen 2.5 VL)

Production-ready local web app for high-volume image OCR and semantic marketing analysis.

## Features
- Drag/drop single, multi-file, and folder uploads.
- Local-only inference (no cloud APIs).
- Qwen 2.5 VL OCR + meaning extraction.
- Real-time per-file and global progress via WebSockets.
- Detailed logs with timestamps, warnings, retries, and traces.
- Timeout handling and per-item retry.
- Duplicate image detection (SHA-256).
- Batch resume from persisted session state.
- Search/sort results.
- Export CSV/XLSX/PDF.
- Premium black/white responsive UI with light/dark switch.

## Output schema per image
- `visible_text` (line breaks preserved when possible)
- `marketing_intent` (`branding`, `awareness`, `conversion`, `product promo`, `CTA`, `informational`, `unclear`)
- `importance_score` (1-10 integer)
- `confidence_score` (0-1 estimate)
- `processing_status`

## Project structure
- `app/`
- `backend/`
- `frontend/`
- `models/`
- `output/`
- `start.py`
- `requirements.txt`
- `README.md`

## Quick start
```bash
python start.py
```

`start.py` will:
1. Install Python dependencies.
2. Install frontend dependencies.
3. Download Qwen 2.5 VL model if missing.
4. Start backend (FastAPI, :8000).
5. Start frontend (Vite, :5173).
6. Wait until both are ready.
7. Open browser automatically.

## Manual start (optional)
```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
python -m uvicorn backend.main:app --reload
# in another terminal
cd frontend && npm run dev
```

## Notes
- CPU-first by default for Windows compatibility and stable local behavior.
- Model is loaded once and reused for queue processing.
- Results and uploads persist in `output/` for resume support.
