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
from cuti.daily import (GalleryReconcileReport, ReconcileReport, queue_is_drained,
                        queue_state, reconcile_missing_lot_galleries,
                        reconcile_missing_lot_images, recover_permanent_image_failures)
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


def _print_gallery_reconcile(report: GalleryReconcileReport) -> None:
    print(
        f"[GALLERY] Candidates: {report.candidates}, Resolved: {report.resolved}, "
        f"Images Added: {report.images_stored}, Missing: {len(report.missing)}, "
        f"Failures: {len(report.failures)}", flush=True,
    )
    for lot_id in report.missing:
        print(f"[UNRESOLVED GALLERY] lot={lot_id} missing gallery in HTML", file=sys.stderr, flush=True)
    for error in report.failures:
        print(f"[UNRESOLVED GALLERY] {error}", file=sys.stderr, flush=True)


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


def _run_refine(conn: Any, settings: Any) -> list[str]:
    """Run Gemini LLM refinement for materialized source snapshots if configured."""
    import sqlite3

    if not isinstance(conn, sqlite3.Connection):
        return []

    db_path = getattr(settings, "db_path", None)
    if db_path is None:
        return []

    cookie_path = getattr(settings, "gemini_cookie_path", None)
    if cookie_path is None and hasattr(db_path, "parent"):
        candidate = Path(db_path).parent / "gemini_cookie.json"
        if candidate.is_file():
            cookie_path = candidate

    if not cookie_path or not Path(cookie_path).is_file():
        print("[STAGE-4:REFINE] Skip: Gemini cookie not configured", flush=True)
        return []

    try:
        from run_llm_refine import count_unrefined_lots, run_refinement
    except ImportError as exc:
        print(f"[ERROR] [STAGE-4:REFINE] Cannot load refine module: {exc}", flush=True)
        return []

    try:
        unrefined = count_unrefined_lots(conn, force=False)
        if unrefined == 0:
            print("[SUMMARY] [STAGE-4:REFINE] 100% lots already refined", flush=True)
            return []

        print(f"[STAGE-4:REFINE] Starting Gemini refinement ({unrefined} lots)...", flush=True)
        processed, success, errors = run_refinement(
            conn,
            cookie_path=cookie_path,
            batch_size=3,
            delay=2.0,
            model="gemini-flash",
            should_update=True,
        )
        remaining = count_unrefined_lots(conn, force=False)
        print(
            f"[SUMMARY] [STAGE-4:REFINE] processed={processed} | success={success} | remaining={remaining}",
            flush=True,
        )
        return errors
    except Exception as exc:
        print(f"[ERROR] [STAGE-4:REFINE] LLM refinement error: {exc}", file=sys.stderr, flush=True)
        return [f"refine error: {exc}"]


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
                    print(f"[ERROR] [STAGE-1:CRAWL] Producer failure: {exc}", flush=True)
                    producer_ok, producer_errors = False, [f"producer source failure: {exc}"]
                errors.extend(producer_errors)
                try:
                    reconcile = reconcile_missing_lot_images(conn, settings, now, api=api)
                    _print_reconcile(reconcile)
                    if reconcile.missing or reconcile.failures:
                        errors.append("image reconciliation incomplete")
                except Exception as exc:
                    errors.append(f"image reconciliation failed: {exc}")
                if not getattr(settings, "details_enabled", False):
                    try:
                        gallery_limit = getattr(settings, "gallery_reconcile_limit", 20)
                        gallery_report = reconcile_missing_lot_galleries(conn, settings, now, limit=gallery_limit)
                        _print_gallery_reconcile(gallery_report)
                    except Exception as exc:
                        errors.append(f"gallery reconciliation failed: {exc}")
                if not producer_ok:
                    errors.append("producer incomplete")

                # Stage 4: Gemini LLM Refinement
                refine_errors = _run_refine(conn, settings)
                errors.extend(refine_errors)

                # Stage 5: Telegram Image Queue Draining
                img_state_before = queue_state(conn) or {}
                pending_before = img_state_before.get("pending", 0)
                print(f"[STAGE-5:TELEGRAM] Syncing images (queue: {pending_before})", flush=True)
                worker_error = _wait_for_drain(conn, worker, sleep)
                if worker_error:
                    errors.append(worker_error)
                img_state_after = queue_state(conn) or {}
                if img_state_after.get("permanent_error", 0):
                    recovered = recover_permanent_image_failures(conn, settings, now)
                    if recovered:
                        print(f"[STAGE-5:TELEGRAM] Recovered {recovered} failed images via retry", flush=True)
                    img_state_after = queue_state(conn) or {}
                up_cnt = img_state_after.get("ready", 0)
                rem_cnt = img_state_after.get("pending", 0)
                fail_cnt = img_state_after.get("permanent_error", 0)
                print(
                    f"[SUMMARY] [STAGE-5:TELEGRAM] uploaded={up_cnt} | remaining={rem_cnt} | failed={fail_cnt}",
                    flush=True,
                )
                if count_lot_images(conn)["permanent_error"]:
                    errors.append("permanent image failures remain")
                _stop_worker(worker, parent_connection)
                worker = None
                parent_connection = None
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
