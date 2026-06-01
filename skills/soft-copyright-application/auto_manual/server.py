"""Start/stop IP Agent dev servers and wait until healthy."""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _probe(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def wait_for_servers(
    frontend_url: str,
    backend_health_url: str,
    *,
    timeout_sec: int = 120,
    interval: float = 2.0,
) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        fe = _probe(frontend_url)
        be = _probe(backend_health_url)
        if fe and be:
            return
        time.sleep(interval)
    raise TimeoutError(
        f"Servers not ready within {timeout_sec}s\n"
        f"  frontend {frontend_url}: {_probe(frontend_url)}\n"
        f"  backend  {backend_health_url}: {_probe(backend_health_url)}"
    )


def run_seed_demo(project_root: Path) -> None:
    import os

    backend = project_root / "backend"
    python = backend / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        python = Path(sys.executable)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.run(
        [str(python), "-m", "app.scripts.seed_demo"],
        cwd=str(backend),
        check=True,
        env=env,
    )


def start_servers(project_root: Path) -> tuple[subprocess.Popen, subprocess.Popen]:
    import os

    backend = project_root / "backend"
    frontend = project_root / "frontend"
    python = backend / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        raise FileNotFoundError(f"Backend venv not found: {python}. Run scripts/dev.ps1 once.")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    backend_proc = subprocess.Popen(
        [str(python), "-m", "uvicorn", "app.main:app", "--port", "8000"],
        cwd=str(backend),
        env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    time.sleep(2)
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host=127.0.0.1", "--port=5173"],
        cwd=str(frontend),
        shell=sys.platform == "win32",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    return backend_proc, frontend_proc


def stop_process(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            proc.terminate()
            proc.wait(timeout=10)
    except Exception:
        proc.kill()
