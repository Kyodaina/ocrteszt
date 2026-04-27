from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
import venv
import webbrowser
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "5173"))


def info(msg: str) -> None:
    print(f"[start] {msg}")


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    info("$ " + " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None, env=env)


def py_bin() -> Path:
    return VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_venv() -> None:
    if not VENV_DIR.exists():
        info("Creating virtual environment...")
        venv.create(VENV_DIR, with_pip=True)


def ensure_backend_deps() -> None:
    run([str(py_bin()), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(py_bin()), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])


def ensure_frontend_deps() -> None:
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm is required. Install Node.js LTS and retry.")
    run([npm, "install"], cwd=ROOT / "frontend")


def ensure_model_cache() -> None:
    script = "from transformers import AutoProcessor, AutoModelForVision2Seq; m='Qwen/Qwen2.5-VL-3B-Instruct'; AutoProcessor.from_pretrained(m, cache_dir='models'); AutoModelForVision2Seq.from_pretrained(m, cache_dir='models', trust_remote_code=True); print('model ready')"
    run([str(py_bin()), "-c", script], cwd=ROOT)


def wait_http(url: str, timeout: float = 180.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urlopen(url, timeout=2) as r:
                if r.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main() -> None:
    info(f"Platform: {platform.platform()}")
    info(f"Python: {sys.version.split()[0]}")
    ensure_venv()
    ensure_backend_deps()
    ensure_frontend_deps()
    ensure_model_cache()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)

    backend_cmd = [str(py_bin()), "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)]
    frontend_cmd = [shutil.which("npm") or "npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(FRONTEND_PORT)]

    info("Starting backend...")
    backend = subprocess.Popen(backend_cmd, cwd=ROOT, env=env)
    info("Starting frontend...")
    frontend = subprocess.Popen(frontend_cmd, cwd=ROOT / "frontend", env=env)

    try:
        backend_ready = wait_http(f"http://127.0.0.1:{BACKEND_PORT}/api/health")
        frontend_ready = wait_http(f"http://127.0.0.1:{FRONTEND_PORT}")
        info(f"Backend ready: {backend_ready}")
        info(f"Frontend ready: {frontend_ready}")
        if backend_ready and frontend_ready:
            webbrowser.open(f"http://127.0.0.1:{FRONTEND_PORT}")
            info("Opened browser")
        info("Press Ctrl+C to stop")
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        info("Stopping services...")
        backend.terminate()
        frontend.terminate()


if __name__ == "__main__":
    main()
