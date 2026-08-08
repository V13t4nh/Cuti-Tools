"""Run tests and a real sample-data workflow in an isolated project-local directory."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(arguments: list[str], env: dict[str, str]) -> None:
    print(f"\n> {' '.join(arguments)}", flush=True)
    subprocess.run(arguments, cwd=PROJECT_ROOT, env=env, check=True)


def main() -> int:
    run_dir = PROJECT_ROOT / "var" / "verify" / uuid.uuid4().hex[:12]
    run_dir.mkdir(parents=True, exist_ok=False)
    test_env = {key: value for key, value in os.environ.items() if not key.startswith("CUTI_")}
    python = sys.executable
    _run([python, "-m", "unittest", "discover", "-s", "tests", "-v"], test_env)

    env = dict(test_env)
    env.update(
        {
            "CUTI_HOME": str(PROJECT_ROOT),
            "CUTI_DB_PATH": str(run_dir / "auctions.db"),
            "CUTI_NOTIFIER_FILE_PATH": str(run_dir / "alerts.jsonl"),
            "CUTI_REPORT_PATH": str(run_dir / "report.html"),
            "CUTI_LOTS_SOURCE_URL": str(
                PROJECT_ROOT / "data" / "sample" / "catawiki" / "page-1.html"
            ),
            "CUTI_DEALS_SOURCE_URL": str(
                PROJECT_ROOT / "data" / "sample" / "deals" / "deals.json"
            ),
        }
    )
    base = [python, "-m", "cuti.cli", "--home", str(PROJECT_ROOT), "--today", "2026-08-01"]
    for command in (
        ["--json", "init-db"],
        ["--json", "ingest"],
        [
            "--json",
            "quote",
            "--title",
            "Omega Speedmaster Professional 311.30.42 full set",
            "--cost-vnd",
            "30000000",
            "--condition",
            "fullset",
            "--form",
            "round",
        ],
        ["--json", "watch"],
        ["--json", "liquidity"],
        ["--json", "report"],
        ["--json", "status"],
    ):
        _run([*base, *command], env)
    print(f"\nVERIFY OK — artifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
