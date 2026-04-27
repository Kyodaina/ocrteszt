from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
OUTPUT_DIR = BASE_DIR / "output"
UPLOAD_DIR = OUTPUT_DIR / "uploads"
STATE_FILE = OUTPUT_DIR / "session_state.json"

MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
DEFAULT_TIMEOUT_SECONDS = 90
MAX_WORKERS = 2

for path in (MODELS_DIR, OUTPUT_DIR, UPLOAD_DIR):
    path.mkdir(parents=True, exist_ok=True)
