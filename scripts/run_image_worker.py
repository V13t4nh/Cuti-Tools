"""Long-running durable worker for the SQLite-backed Telegram image queue."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cuti.config import load_settings
from cuti.storage import connect
from cuti.telegram_media import process_lot_image_queue, require_telegram_credentials
from process_lock import ProcessLockBusy, process_lock


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be greater than zero") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Continuously process queued lot images.")
    parser.add_argument("--limit", type=_positive_int, default=20,
                        help="maximum images per active batch (default: 20)")
    parser.add_argument("--poll-seconds", type=_positive_float, default=30.0,
                        help="seconds to sleep when the queue is idle (default: 30)")
    return parser.parse_args(argv)


def _control_status(parent_connection: object | None) -> str:
    if parent_connection is None:
        return "alive"
    try:
        if not parent_connection.poll(0):
            return "alive"
        return "stop" if parent_connection.recv() == "stop" else "alive"
    except (EOFError, OSError):
        return "parent-dead"


def _wait_or_parent_exit(parent_connection: object | None, seconds: float) -> str:
    if parent_connection is None:
        time.sleep(seconds)
        return "alive"
    deadline = time.monotonic() + seconds
    while True:
        status = _control_status(parent_connection)
        if status != "alive":
            return status
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "alive"
        try:
            parent_connection.poll(min(0.5, remaining))
        except (EOFError, OSError):
            return "parent-dead"


def _run(settings: object, limit: int, poll_seconds: float, parent_connection: object | None = None) -> int:
    lock_path = settings.db_path.with_suffix(settings.db_path.suffix + ".image.lock")
    with process_lock(lock_path, "image worker is already running"), connect(settings.db_path) as conn:
        require_telegram_credentials(settings)
        if parent_connection is not None:
            parent_connection.send("ready")
        print(f"[START] Image worker running (limit={limit}, poll_seconds={poll_seconds:g})", flush=True)
        while True:
            status = _control_status(parent_connection)
            if status == "stop":
                print("[STOP] Daily parent requested worker shutdown", flush=True)
                return 0
            if status == "parent-dead":
                print("[STOP] Daily parent exited", file=sys.stderr, flush=True)
                return 3
            now = datetime.now(timezone.utc)
            result = process_lot_image_queue(conn, settings, now, limit=limit)
            failed = result["failed"]
            print(
                f"[BATCH] Candidates: {result['candidates']}, Uploaded: {result['uploaded']}, "
                f"Failed: {len(failed)}",
                flush=True,
            )
            for item in failed:
                print(
                    f"[FAIL] lot={item['lot_id']} idx={item['idx']} "
                    f"state={item['state']} error={item['error']}",
                    file=sys.stderr,
                    flush=True,
                )
            if result["candidates"]:
                continue
            print(f"[IDLE] No queued images; sleeping {poll_seconds:g}s", flush=True)
            status = _wait_or_parent_exit(parent_connection, poll_seconds)
            if status == "stop":
                print("[STOP] Daily parent requested worker shutdown", flush=True)
                return 0
            if status == "parent-dead":
                print("[STOP] Daily parent exited", file=sys.stderr, flush=True)
                return 3


def worker_process_entry(settings: object, parent_connection: object) -> int:
    """Multiprocessing entrypoint used by the daily launcher."""
    try:
        return _run(settings, 20, 30.0, parent_connection)
    except ProcessLockBusy as exc:
        try:
            parent_connection.send("busy")
        except (OSError, EOFError):
            pass
        print(f"[BUSY] {exc}", file=sys.stderr, flush=True)
        return 2
    except Exception as exc:
        try:
            parent_connection.send("error")
        except (OSError, EOFError):
            pass
        print(f"[ERROR] image worker failed: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        parent_connection.close()


def worker_process_main(settings: object, parent_connection: object) -> None:
    """Multiprocessing target that propagates the worker status as an exit code."""
    raise SystemExit(worker_process_entry(settings, parent_connection))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        settings = load_settings(base_dir=PROJECT_ROOT)
        return _run(settings, args.limit, args.poll_seconds)
    except ProcessLockBusy as exc:
        print(f"[BUSY] {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("[STOP] Image worker stopped by Ctrl+C", flush=True)
        return 130
    except Exception as exc:
        print(f"[ERROR] image worker failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
