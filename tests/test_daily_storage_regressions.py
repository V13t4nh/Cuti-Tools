"""Offline regressions for daily missing-cover discovery and atomic writes."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from cuti.storage import (
    LiveWatchRow,
    claim_lot_image,
    connect,
    fetch_lot_image,
    mark_lot_image_failed,
    mark_lot_image_ready,
    upsert_live_watch,
    upsert_lots,
    upsert_lot_image,
)
from daily_crawl_harness import block_network
from support import NOW, make_lot, settings_for


class DailyStorageRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="cuti-daily-storage-"))
        self.addCleanup(self._cleanup)
        self.conn = connect(self.temp_dir / "isolated.db")
        self.network_guard = block_network()
        self.network_guard.__enter__()
        self.addCleanup(self.network_guard.__exit__, None, None, None)
        self.settings = settings_for(self.temp_dir, CUTI_NOTIFIER="file")

    def _cleanup(self) -> None:
        self.conn.close()
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_missing_cover_ids_are_distinct_union_of_lots_and_live_watch(self) -> None:
        from cuti.storage.media import find_lot_ids_missing_cover

        upsert_lots(
            self.conn,
            [
                make_lot("db-only-lot"),
                make_lot("covered-lot"),
                make_lot("overlap-lot"),
            ],
            NOW,
        )
        upsert_live_watch(
            self.conn,
            [
                LiveWatchRow("live-only-lot", "catawiki", "Live", None, "https://source.invalid/live", None),
                LiveWatchRow("covered-lot", "catawiki", "Covered", None, "https://source.invalid/covered", None),
                LiveWatchRow("overlap-lot", "catawiki", "Overlap", None, "https://source.invalid/overlap", None),
            ],
            NOW,
        )
        upsert_lot_image(
            self.conn,
            lot_id="covered-lot",
            idx=0,
            source_url="https://source.invalid/images/covered.jpg",
        )
        self.conn.commit()
        self.assertEqual(
            find_lot_ids_missing_cover(self.conn),
            ["db-only-lot", "live-only-lot", "overlap-lot"],
        )

    def test_atomic_live_watch_and_cover_write_rolls_back_on_image_crash(self) -> None:
        from cuti.storage.watch import upsert_live_watch_with_images

        self.conn.executescript(
            """
            CREATE TRIGGER fail_daily_cover_insert
            BEFORE INSERT ON lot_images
            BEGIN
                SELECT RAISE(ABORT, 'simulated image persistence crash');
            END;
            """
        )
        row = LiveWatchRow(
            "atomic-lot",
            "catawiki",
            "Atomic",
            None,
            "https://source.invalid/atomic",
            None,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            upsert_live_watch_with_images(
                self.conn,
                [row],
                {"atomic-lot": "https://source.invalid/images/atomic.jpg"},
                NOW,
            )
        self.assertIsNone(
            self.conn.execute("SELECT 1 FROM live_watch WHERE lot_id='atomic-lot'").fetchone()
        )
        self.assertIsNone(fetch_lot_image(self.conn, "atomic-lot"))

    def test_future_retry_and_live_lease_keep_queue_nonterminal(self) -> None:
        from cuti.daily import queue_is_drained, queue_state

        for lot_id in ("lease-lot", "retry-lot"):
            upsert_lot_image(
                self.conn,
                lot_id=lot_id,
                idx=0,
                source_url=f"https://source.invalid/images/{lot_id}.jpg",
            )
        self.conn.commit()
        lease = claim_lot_image(
            self.conn, worker_id="lease-owner", now=NOW, lease_seconds=30
        )
        retry = claim_lot_image(
            self.conn, worker_id="retry-owner", now=NOW, lease_seconds=30
        )
        self.assertEqual(lease["lot_id"], "lease-lot")
        self.assertEqual(retry["lot_id"], "retry-lot")
        mark_lot_image_failed(
            self.conn,
            lot_id="retry-lot",
            idx=0,
            worker_id="retry-owner",
            error="retry later",
            now=NOW,
            retryable=True,
            max_attempts=3,
            base_pause_seconds=60,
            max_backoff_seconds=120,
        )
        self.assertEqual(queue_state(self.conn)["pending"], 2)
        self.assertFalse(queue_is_drained(self.conn))
        mark_lot_image_ready(
            self.conn,
            lot_id="lease-lot",
            idx=0,
            worker_id="lease-owner",
            file_id="fake-lease-file",
            file_path=None,
            message_id=1,
            uploaded_at=NOW,
        )
        retry = claim_lot_image(
            self.conn,
            worker_id="retry-owner-2",
            now=NOW + timedelta(seconds=60),
            lease_seconds=30,
        )
        self.assertEqual(retry["lot_id"], "retry-lot")
        mark_lot_image_ready(
            self.conn,
            lot_id="retry-lot",
            idx=0,
            worker_id="retry-owner-2",
            file_id="fake-retry-file",
            file_path=None,
            message_id=2,
            uploaded_at=NOW,
        )
        self.assertTrue(queue_is_drained(self.conn))


if __name__ == "__main__":
    unittest.main()
