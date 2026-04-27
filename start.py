from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print('>', ' '.join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def ensure_python_deps() -> None:
    run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], ROOT)


def ensure_node_deps() -> None:
    if not (ROOT / 'frontend' / 'node_modules').exists():
        run(['npm', 'install'], ROOT / 'frontend')


def ensure_model() -> None:
    models_dir = ROOT / 'models'
    expected = models_dir / 'models--Qwen--Qwen2.5-VL-3B-Instruct'
    if expected.exists():
        return
    snippet = (
        'from transformers import AutoProcessor,Qwen2_5_VLForConditionalGeneration;'
        'AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-3B-Instruct",cache_dir="models",trust_remote_code=True);'
        'Qwen2_5_VLForConditionalGeneration.from_pretrained("Qwen/Qwen2.5-VL-3B-Instruct",cache_dir="models",trust_remote_code=True)'
    )
    run([sys.executable, '-c', snippet], ROOT)


def wait_for(url: str, timeout: int = 120) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urlopen(url, timeout=2):
                return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f'{url} did not become ready in time')


def main() -> None:
    ensure_python_deps()
    ensure_node_deps()
    ensure_model()

    backend = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000'], cwd=ROOT)
    frontend = subprocess.Popen(['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173'], cwd=ROOT / 'frontend')

    try:
        wait_for('http://127.0.0.1:8000/api/snapshot')
        wait_for('http://127.0.0.1:5173')
        webbrowser.open('http://127.0.0.1:5173')
        print('Application ready at http://127.0.0.1:5173')
        backend.wait()
    finally:
        if frontend.poll() is None:
            frontend.terminate()
        if backend.poll() is None:
            backend.terminate()


if __name__ == '__main__':
    if os.name == 'nt':
        os.system('')
    main()
