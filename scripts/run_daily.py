"""Single-command scheduled crawl, reconciliation and image draining."""

from __future__ import annotations

import multiprocessing
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from cuti.config import load_settings
from cuti.daily import ReconcileReport, queue_is_drained, queue_state, reconcile_missing_lot_images
from cuti.errors import FetchError, NormalizationError, ScrapeError
from cuti.normalize import load_rules
from cuti.storage import connect, count_lot_images
from process_lock import ProcessLockBusy, process_lock
from run_image_worker import worker_process_main
from run_scheduled_crawl import run_scheduled_flow

_run_producer = run_scheduled_flow


def start_worker_process(settings: Any) -> tuple[multiprocessing.Process, Any]:
    """Start one supervised worker and return its process and parent sentinel."""
    context = multiprocessing.get_context("spawn")
    parent_connection, child_connection = context.Pipe(duplex=True)
    process = context.Process(target=worker_process_main, args=(settings, child_connection), name="cuti-image-worker")
    started = False
    try:
        process.start()
        started = True
        deadline = time.monotonic() + 5.0
        while not parent_connection.poll(0.1):
            if not process.is_alive():
                raise RuntimeError(f"image worker exited before startup (code {process.exitcode})")
            if time.monotonic() >= deadline:
                raise RuntimeError("image worker startup handshake timed out")
        status = parent_connection.recv()
        if status == "busy":
            raise ProcessLockBusy("image worker is already running")
        if status != "ready":
            raise RuntimeError("image worker failed startup")
        child_connection.close()
        return process, parent_connection
    except BaseException:
        if started:
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)
        child_connection.close()
        parent_connection.close()
        raise


def _print_reconcile(report: ReconcileReport) -> None:
    print(
        f"[RECONCILE] Candidates: {report.candidates}, Queued: {report.queued}, "
        f"Missing: {len(report.missing)}, Failures: {len(report.failures)}", flush=True,
    )
    for lot_id in report.missing:
        print(f"[UNRESOLVED] lot={lot_id} missing cover", file=sys.stderr, flush=True)
    for error in report.failures:
        print(f"[UNRESOLVED] {error}", file=sys.stderr, flush=True)


def _wait_for_drain(
    conn: Any,
    process: multiprocessing.Process | None,
    worker_available_or_sleep: bool | Callable[[float], None],
    sleep: Callable[[float], None] | None = None,
) -> str | None:
    if sleep is None:
        sleep = worker_available_or_sleep
    while not queue_is_drained(conn):
        if process is None:
            return "image worker is unavailable while queue is pending"
        if not process.is_alive():
            if process.exitcode == 2:
                return "image worker is already running"
            return f"image worker exited with code {process.exitcode}"
        sleep(0.5)
    if process is not None and not process.is_alive():
        return f"image worker exited with code {process.exitcode}"
    return None


def _stop_worker(process: multiprocessing.Process | None, parent_connection: Any) -> None:
    if process is None:
        if parent_connection is not None:
            parent_connection.close()
        return
    if parent_connection is not None:
        try:
            parent_connection.send("stop")
        except (BrokenPipeError, EOFError, OSError):
            pass
        parent_connection.close()
    process.join(timeout=5)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
    if process.is_alive():
        process.kill()
        process.join()


def run_daily(*, settings: Any = None, now: datetime | None = None, api: Any = None,
              sleep: Callable[[float], None] = time.sleep) -> int:
    settings = settings or load_settings(base_dir=PROJECT_ROOT)
    rules = load_rules(settings.rules_path)
    now = now or datetime.now(timezone.utc)
    daily_lock_path = settings.db_path.with_suffix(settings.db_path.suffix + ".daily.lock")
    crawl_lock_path = settings.db_path.with_suffix(settings.db_path.suffix + ".crawl.lock")
    worker: multiprocessing.Process | None = None
    parent_connection: Any = None
    errors: list[str] = []
    try:
        with process_lock(daily_lock_path, "daily run is already running"), \
             process_lock(crawl_lock_path, "scheduled crawl is already running"):
            worker, parent_connection = start_worker_process(settings)
            with connect(settings.db_path) as conn:
                try:
                    producer_ok, producer_errors = _run_producer(conn, settings, rules, now, api=api)
                except (FetchError, NormalizationError, ScrapeError) as exc:
                    producer_ok, producer_errors = False, [f"producer source failure: {exc}"]
                errors.extend(producer_errors)
                try:
                    reconcile = reconcile_missing_lot_images(conn, settings, now, api=api)
                    _print_reconcile(reconcile)
                    if reconcile.missing or reconcile.failures:
                        errors.append("image reconciliation incomplete")
                except Exception as exc:
                    errors.append(f"image reconciliation failed: {exc}")
                if not producer_ok:
                    errors.append("producer incomplete")
                worker_error = _wait_for_drain(conn, worker, sleep)
                if worker_error:
                    errors.append(worker_error)
                print(f"[IMAGES] {queue_state(conn)}", flush=True)
                if count_lot_images(conn)["permanent_error"]:
                    errors.append("permanent image failures remain")
    except ProcessLockBusy as exc:
        print(f"[BUSY] {exc}", file=sys.stderr, flush=True)
        return 2
    except KeyboardInterrupt:
        print("[STOP] Daily run interrupted by Ctrl+C", file=sys.stderr, flush=True)
        errors.append("interrupted")
    except Exception as exc:
        errors.append(f"daily run failed: {exc}")
    finally:
        _stop_worker(worker, parent_connection)
    for error in errors:
        print(f"[ERROR] {error}", file=sys.stderr, flush=True)
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        print("run_daily.py does not accept command-line options", file=sys.stderr)
        return 2
    return run_daily()


if __name__ == "__main__":
    raise SystemExit(main())
