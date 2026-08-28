"""Scheduled crawler with smart skip logic.

If the database was updated recently (e.g. within 2.5 hours by the local worker),
this runner gracefully skips to avoid duplicate scraping.
"""

from __future__ import annotations

import sys
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cuti.config import load_settings
from cuti.normalize import load_rules
from cuti.pipeline import settle_lots, watch_live
from cuti.storage import connect, count_rows
from process_lock import ProcessLockBusy, process_lock


class CrawlAlreadyRunning(RuntimeError):
    """A second scheduler instance could not acquire the process lock."""


@contextmanager
def _crawl_lock(path: Path):
    """Hold a non-blocking OS lock that is released automatically on process exit."""
    try:
        with process_lock(path, "scheduled crawl is already running"):
            yield
    except ProcessLockBusy as exc:
        raise CrawlAlreadyRunning(str(exc)) from exc


def _is_recently_updated(conn: object, max_age_hours: float = 2.5) -> bool:
    if max_age_hours <= 0:
        raise ValueError("freshness threshold must be positive")
    row = conn.execute(
        """
        SELECT MAX(updated_at) FROM (
            SELECT MAX(updated_at) AS updated_at FROM lots
            UNION ALL
            SELECT MAX(last_seen_at) AS updated_at FROM live_watch
        )
        """
    ).fetchone()
    raw = row[0] if row else None
    if raw is None:
        return False
    try:
        last_time = datetime.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"invalid freshness timestamp in lots.updated_at/live_watch.last_seen_at: {raw!r}"
        ) from exc
    if last_time.tzinfo is None:
        raise RuntimeError(
            f"freshness timestamp has no timezone in lots.updated_at/live_watch.last_seen_at: {raw!r}"
        )
    age = (datetime.now(timezone.utc) - last_time.astimezone(timezone.utc)).total_seconds() / 3600.0
    if age < 0:
        raise RuntimeError(f"freshness timestamp is in the future: {raw!r}")
    if age < max_age_hours:
        print(
            f"[SKIP] Database was already updated {age:.1f}h ago "
            f"(threshold: {max_age_hours}h). Skipping scheduled crawl."
        )
        return True
    return False


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the scheduled watch-live and settle crawl.")
    parser.add_argument("--force", action="store_true", help="run even when data was updated recently")
    return parser.parse_args(argv)


def run_scheduled_flow(conn: object, settings: object, rules: object, now: datetime,
                       *, api: object = None, force: bool = False) -> tuple[bool, list[str]]:
    """Run the shared freshness-guarded watch-live and settlement sequence."""
    if not force and _is_recently_updated(conn):
        print("[SKIP] Fresh database; crawl and settlement skipped.", flush=True)
        return True, []
    errors: list[str] = []
    print("[START] Running scheduled watch-live...", flush=True)
    watch_rep = watch_live(conn, settings, now, api=api)
    print(
        f"[WATCH-LIVE] Seen: {watch_rep.lots_seen}, Tracked: {watch_rep.lots_tracked}, "
        f"Queue: {count_rows(conn, 'live_watch')}", flush=True,
    )
    print("[START] Running scheduled settle...", flush=True)
    settle_rep = settle_lots(conn, rules, settings, now.date(), now, api=api)
    print(
        f"[SETTLE] Sold: {settle_rep.sold}, Unsold: {settle_rep.unsold}, "
        f"Lots written: {settle_rep.lots_written}, Lots total: {count_rows(conn, 'lots')}", flush=True,
    )
    errors.extend(settle_rep.errors)
    if settle_rep.details_failed and not settle_rep.errors:
        errors.append(f"{settle_rep.details_failed} detail fetches failed")
    return not errors, errors


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        settings = load_settings(base_dir=PROJECT_ROOT)
        rules = load_rules(settings.rules_path)
        now = datetime.now(timezone.utc)
        lock_path = settings.db_path.with_suffix(settings.db_path.suffix + ".crawl.lock")
        with _crawl_lock(lock_path), connect(settings.db_path) as conn:
            ok, errors = run_scheduled_flow(conn, settings, rules, now, force=args.force)
            for error in errors:
                print(f"[SETTLE-ERROR] {error}", file=sys.stderr)
            return 0 if ok else 1
    except CrawlAlreadyRunning as exc:
        print(f"[SKIP] {exc}")
        return 0
    except Exception as exc:
        print(f"[ERROR] scheduled crawl failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
