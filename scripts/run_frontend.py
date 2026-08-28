"""Run the CUTI API and Vite frontend as one managed command."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def _command(mode: str) -> list[str]:
    executable = "npm.cmd" if os.name == "nt" else "npm"
    return [executable, "run", "dev:ui" if mode == "dev" else "preview:ui"]


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "dev"
    if mode not in {"dev", "preview"}:
        print("usage: run_frontend.py [dev|preview]", file=sys.stderr)
        return 2
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    if mode == "preview":
        npm = "npm.cmd" if os.name == "nt" else "npm"
        built = subprocess.run([npm, "run", "build"], cwd=FRONTEND, env=env, check=False)
        if built.returncode:
            return built.returncode
    api = subprocess.Popen([sys.executable, "-m", "cuti.server", "8000"], cwd=ROOT, env=env)
    ui = subprocess.Popen(_command(mode), cwd=FRONTEND, env=env)
    processes = (api, ui)
    try:
        while all(process.poll() is None for process in processes):
            time.sleep(0.25)
        return next((process.returncode for process in processes if process.returncode), 0)
    except KeyboardInterrupt:
        return 130
    finally:
        for process in processes:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
