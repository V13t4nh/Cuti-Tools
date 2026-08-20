"""Run the hermetic test and sample-data workflow with a raw audit log."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import sys
import traceback
import uuid
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FROZEN_FILES = (
    "src/cuti/pricing.py",
    "src/cuti/storage/schema_ddl.py",
    "config/rules.json",
)


class FrozenFileError(FileNotFoundError):
    """A file required by the frozen-source integrity check is missing."""


def _frozen_sha256(path: Path) -> str:
    if not path.is_file():
        raise FrozenFileError(f"frozen file is missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frozen_markers(root: Path | None = None) -> list[str]:
    root = PROJECT_ROOT if root is None else root
    return [
        f"FROZEN_SHA256 {relative} {_frozen_sha256(root / relative)}"
        for relative in FROZEN_FILES
    ]


class _Log:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open("w", encoding="utf-8", newline="")

    def line(self, text: str = "") -> None:
        self.file.write(text + "\n")
        self.file.flush()

    def write(self, text: str) -> None:
        self.file.write(text)
        self.file.flush()

    def __enter__(self) -> "_Log":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.file.close()


def _environment_trace(log: _Log, env: dict[str, str]) -> None:
    log.line(f"PYTHON={sys.executable}")
    log.line(f"PYTHON_VERSION={sys.version.split()[0]}")
    packages = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--format=freeze"],
        capture_output=True,
        text=True,
        check=False,
    )
    log.line("PACKAGES_BEGIN")
    log.write(packages.stdout)
    if packages.stdout and not packages.stdout.endswith("\n"):
        log.line()
    log.line("PACKAGES_END")
    names = sorted(name for name in env if name.startswith("CUTI_"))
    log.line("CUTI_ENV_NAMES=" + (",".join(names) if names else "(none)"))


def _alerts_sent(db_path: Path) -> int:
    """Read the number of sent alerts from this verification run's database."""
    if not db_path.is_file():
        return 0
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM alert_outbox WHERE status = 'sent'"
        ).fetchone()
    finally:
        conn.close()
    return int(row[0]) if row is not None else 0


def _source_loc_max() -> int:
    return max(
        len(path.read_text(encoding="utf-8").splitlines())
        for path in (PROJECT_ROOT / "src" / "cuti").rglob("*.py")
    )


def _live_fixture_count() -> int:
    fixture_dir = PROJECT_ROOT / "tests" / "fixtures" / "live"
    return sum(1 for path in fixture_dir.glob("*.html") if path.is_file())


def _run(arguments: list[str], env: dict[str, str], log: _Log) -> None:
    command = " ".join(arguments)
    print(f"\n> {command}", flush=True)
    log.line(f"> {command}")
    result = subprocess.run(
        arguments,
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="", flush=True)
        log.write(result.stdout)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, arguments)


def main() -> int:
    day_dir = PROJECT_ROOT / "var" / "verify" / date.today().isoformat()
    run_dir = day_dir / f"run-{uuid.uuid4().hex[:12]}"
    run_dir.mkdir(parents=True, exist_ok=False)
    log_path = day_dir / "verify.log"
    test_env = {key: value for key, value in os.environ.items() if not key.startswith("CUTI_")}
    python = sys.executable
    with _Log(log_path) as log:
        log.line("COMMAND=" + " ".join([python, "scripts/verify.py"]))
        _environment_trace(log, os.environ)
        fixture_marker = f"LIVE_FIXTURES={_live_fixture_count()}"
        print(fixture_marker, flush=True)
        log.line(fixture_marker)
        code = 0
        try:
            _run([python, "-m", "unittest", "discover", "-s", "tests", "-v"], test_env, log)
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
                _run([*base, *command], env, log)
            marker = f"SRC_LOC_MAX={_source_loc_max()}"
            print(marker, flush=True)
            log.line(marker)
            for frozen_marker in _frozen_markers():
                print(frozen_marker, flush=True)
                log.line(frozen_marker)
            success = f"VERIFY OK — artifacts: {run_dir}"
            print(f"\n{success}")
            log.line(success)
        except BaseException:
            code = 1
            traceback.print_exc()
            traceback.print_exc(file=log.file)
        alerts_marker = f"ALERTS_SENT={_alerts_sent(run_dir / 'auctions.db')}"
        print(alerts_marker, flush=True)
        log.line(alerts_marker)
        log.line(f"EXIT={code}")
        return code


if __name__ == "__main__":
    raise SystemExit(main())
