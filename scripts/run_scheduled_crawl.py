"""Scheduled crawler with smart skip logic.

If the database was updated recently (e.g. within 2.5 hours by the local worker),
this runner gracefully skips to avoid duplicate scraping.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cuti.config import load_settings
from cuti.normalize import load_rules
from cuti.pipeline import settle_lots, watch_live
from cuti.storage import connect, count_rows


def _is_recently_updated(conn: object, max_age_hours: float = 2.5) -> bool:
    row = conn.execute("SELECT MAX(created_at) FROM lots").fetchone()
    if row and row[0]:
        try:
            last_time = datetime.fromisoformat(row[0])
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - last_time).total_seconds() / 3600.0
            if age < max_age_hours:
                print(
                    f"[SKIP] Database was already updated {age:.1f}h ago "
                    f"(threshold: {max_age_hours}h). Skipping scheduled crawl."
                )
                return True
        except Exception:
            pass
    return False


def main() -> int:
    settings = load_settings(base_dir=PROJECT_ROOT)
    rules = load_rules(settings.rules_path)
    now = datetime.now(timezone.utc)
    today = now.date()
    with connect(settings.db_path) as conn:
        if "--force" not in sys.argv and _is_recently_updated(conn):
            return 0
        print("[START] Running scheduled watch-live...")
        watch_rep = watch_live(conn, settings, now)
        print(
            f"[WATCH-LIVE] Seen: {watch_rep.lots_seen}, Tracked: {watch_rep.lots_tracked}, "
            f"Queue: {count_rows(conn, 'live_watch')}"
        )
        print("[START] Running scheduled settle...")
        settle_rep = settle_lots(conn, rules, settings, today, now)
        print(
            f"[SETTLE] Sold: {settle_rep.sold}, Unsold: {settle_rep.unsold}, "
            f"Lots written: {settle_rep.lots_written}, Lots total: {count_rows(conn, 'lots')}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
