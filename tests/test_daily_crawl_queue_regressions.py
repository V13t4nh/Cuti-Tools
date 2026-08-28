"""Offline regressions for durable one-cover queue behavior."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cuti.errors import MediaUploadError, StorageError
from cuti.storage import (
    claim_lot_image,
    connect,
    fetch_lot_image,
    mark_lot_image_failed,
    mark_lot_image_ready,
    upsert_lot_image,
)
from cuti.storage.schema_ddl import SCHEMA_SQL
from cuti.pipeline.report import watch_live
from cuti.scrapers import catawiki_api
from cuti.telegram_media import process_lot_image_queue, queue_lot_images
from daily_crawl_harness import FakeClock, FakeTelegramTransport, block_network, callback_transport
from support import settings_for


NOW = datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc)
FIXTURE = Path(__file__).parent / "fixtures" / "daily_crawl" / "telegram_sendphoto_success.json"


class DurableQueueRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="cuti-daily-queue-"))
        self.addCleanup(self._cleanup)
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.network_guard = block_network()
        self.network_guard.__enter__()
        self.addCleanup(self.network_guard.__exit__, None, None, None)
        self.settings = settings_for(
            self.temp_dir,
            CUTI_TELEGRAM_BOT_TOKEN="fake-bot-token",
            CUTI_TELEGRAM_CHAT_ID="-1000000000000",
            CUTI_TELEGRAM_CHANNEL_ID="",
            CUTI_TELEGRAM_UPLOAD_PAUSE_SECONDS="60",
            CUTI_TELEGRAM_UPLOAD_MAX_ATTEMPTS="3",
            CUTI_TELEGRAM_UPLOAD_MAX_BACKOFF_SECONDS="60",
            CUTI_TELEGRAM_UPLOAD_LEASE_SECONDS="30",
        )

    def _cleanup(self) -> None:
        self.conn.close()
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _queue(self, lot_id: str, source_url: str) -> None:
        upsert_lot_image(self.conn, lot_id=lot_id, idx=0, source_url=source_url)
        self.conn.commit()

    def _fixture_result(self) -> dict[str, object]:
        result = json.loads(FIXTURE.read_text(encoding="utf-8"))["result"]
        return {
            "file_id": result["photo"][-1]["file_id"],
            "file_unique_id": result["photo"][-1]["file_unique_id"],
            "file_path": None,
            "message_id": result["message_id"],
        }

    def test_ready_cover_is_not_claimed_or_uploaded_again(self) -> None:
        self._queue("ready-lot", "https://source.invalid/ready.jpg")
        mark = claim_lot_image(
            self.conn, worker_id="seed", now=NOW, lease_seconds=30
        )
        assert mark is not None
        result = self._fixture_result()
        mark_lot_image_ready(
            self.conn,
            lot_id="ready-lot",
            idx=0,
            worker_id="seed",
            file_id=result["file_id"],
            file_path=None,
            message_id=result["message_id"],
            uploaded_at=NOW,
        )
        transport = FakeTelegramTransport([])
        with patch(
            "cuti.telegram_media.upload_image_to_telegram",
            side_effect=callback_transport(transport),
        ):
            report = process_lot_image_queue(
                self.conn, self.settings, NOW, worker_id="worker-a"
            )
        self.assertEqual(report, {"candidates": 0, "uploaded": 0, "failed": []})
        self.assertEqual(transport.calls, [])
        self.assertEqual(fetch_lot_image(self.conn, "ready-lot")["state"], "ready")
        self.assertEqual(fetch_lot_image(self.conn, "ready-lot")["telegram_file_id"], "fake-photo-cover")

    def test_queued_and_expired_leases_are_recovered_but_live_lease_is_not(self) -> None:
        self._queue("live-lot", "https://source.invalid/live.jpg")
        live = claim_lot_image(
            self.conn, worker_id="live-worker", now=NOW, lease_seconds=300
        )
        self.assertEqual(live["lot_id"], "live-lot")
        self._queue("expired-lot", "https://source.invalid/expired.jpg")
        self._queue("queued-lot", "https://source.invalid/queued.jpg")
        self.conn.execute(
            "UPDATE lot_images SET state='uploading', lease_owner='dead-worker', "
            "lease_expires_at=? WHERE lot_id='expired-lot'",
            ((NOW - timedelta(minutes=1)).isoformat(),),
        )
        self.conn.commit()
        transport = FakeTelegramTransport([self._fixture_result(), self._fixture_result()])
        with patch(
            "cuti.telegram_media.upload_image_to_telegram",
            side_effect=callback_transport(transport),
        ):
            report = process_lot_image_queue(
                self.conn, self.settings, NOW, limit=3, worker_id="worker-a", sleep=FakeClock().sleep
            )
        self.assertEqual(report["uploaded"], 2)
        self.assertEqual(
            [call.source_url for call in transport.calls],
            ["https://source.invalid/expired.jpg", "https://source.invalid/queued.jpg"],
        )
        self.assertEqual(fetch_lot_image(self.conn, "expired-lot")["state"], "ready")
        self.assertEqual(fetch_lot_image(self.conn, "queued-lot")["state"], "ready")
        self.assertEqual(fetch_lot_image(self.conn, "live-lot")["state"], "uploading")

    def test_retryable_failure_waits_until_due_then_succeeds(self) -> None:
        self._queue("retry-lot", "https://source.invalid/retry.jpg")
        transport = FakeTelegramTransport(
            [MediaUploadError("retryable transport failure"), self._fixture_result()]
        )
        with patch(
            "cuti.telegram_media.upload_image_to_telegram",
            side_effect=callback_transport(transport),
        ):
            clock = FakeClock()
            first = process_lot_image_queue(
                self.conn, self.settings, NOW, worker_id="worker-a", sleep=clock.sleep
            )
            early = process_lot_image_queue(
                self.conn,
                self.settings,
                NOW + timedelta(seconds=59),
                worker_id="worker-a",
                sleep=clock.sleep,
            )
            due = process_lot_image_queue(
                self.conn,
                self.settings,
                NOW + timedelta(seconds=60),
                worker_id="worker-a",
                sleep=clock.sleep,
            )
        self.assertEqual(first["failed"][0]["state"], "retryable_error")
        self.assertEqual(early["candidates"], 0)
        self.assertEqual(due["uploaded"], 1)
        self.assertEqual(len(transport.calls), 2)

    def test_retryable_failure_exhaustion_is_permanent_and_retained(self) -> None:
        settings = settings_for(
            self.temp_dir,
            CUTI_TELEGRAM_BOT_TOKEN="fake-bot-token",
            CUTI_TELEGRAM_CHAT_ID="-1000000000000",
            CUTI_TELEGRAM_UPLOAD_MAX_ATTEMPTS="1",
            CUTI_TELEGRAM_UPLOAD_PAUSE_SECONDS="0",
        )
        self._queue("permanent-lot", "https://source.invalid/permanent.jpg")
        transport = FakeTelegramTransport([MediaUploadError("retryable transport failure")])
        with patch(
            "cuti.telegram_media.upload_image_to_telegram",
            side_effect=callback_transport(transport),
        ):
            report = process_lot_image_queue(self.conn, settings, NOW, worker_id="worker-a")
        self.assertEqual(report["failed"][0]["state"], "permanent_error")
        row = fetch_lot_image(self.conn, "permanent-lot")
        self.assertEqual(row["state"], "permanent_error")
        self.assertIsNone(row["next_attempt_at"])
        self.assertEqual(row["attempts"], 1)

    def test_lease_owner_is_required_to_finalize_a_cover(self) -> None:
        self._queue("owned-lot", "https://source.invalid/owned.jpg")
        claim = claim_lot_image(self.conn, worker_id="owner-a", now=NOW, lease_seconds=30)
        self.assertIsNotNone(claim)
        with self.assertRaises(StorageError):
            mark_lot_image_ready(
                self.conn,
                lot_id="owned-lot",
                idx=0,
                worker_id="owner-b",
                file_id="wrong-owner",
                file_path=None,
                message_id=1,
                uploaded_at=NOW,
            )
        row = fetch_lot_image(self.conn, "owned-lot")
        self.assertEqual(row["state"], "uploading")
        self.assertEqual(row["lease_owner"], "owner-a")

    def test_cover_url_is_immutable_once_slot_exists(self) -> None:
        self._queue("immutable-lot", "https://source.invalid/original.jpg")
        with self.assertRaises(StorageError):
            upsert_lot_image(
                self.conn,
                lot_id="immutable-lot",
                idx=0,
                source_url="https://source.invalid/changed.jpg",
            )
        self.assertEqual(
            fetch_lot_image(self.conn, "immutable-lot")["source_url"],
            "https://source.invalid/original.jpg",
        )

    def test_watch_live_cover_failure_does_not_leave_a_tracked_lot(self) -> None:
        """A crash between real watch tracking and cover persistence is atomic."""
        settings = settings_for(
            self.temp_dir,
            CUTI_CATAWIKI_QUERIES="watch",
            CUTI_CATAWIKI_SEARCH_MAX_PAGES="1",
            CUTI_CATAWIKI_BATCH_SIZE="10",
            CUTI_CATAWIKI_PAUSE_SECONDS="0",
        )
        ref = catawiki_api.LotRef(
            lot_id="atomic-lot",
            title="Atomic test",
            subtitle=None,
            url="https://source.invalid/l/atomic",
            image_url="https://source.invalid/atomic.jpg",
        )
        fake_api = SimpleNamespace(
            requests_made=0,
            search=lambda _query, _page: catawiki_api.SearchPage(total=1, lots=(ref,)),
            live_states=lambda lot_ids: {
                lot_id: catawiki_api.LiveState(
                    lot_id, False, 1, NOW.date(), NOW.date() + timedelta(days=1), None
                )
                for lot_id in lot_ids
            },
        )
        with patch(
            "cuti.storage.upsert_lot_image",
            side_effect=RuntimeError("simulated cover persistence crash"),
        ):
            with self.assertRaises(RuntimeError):
                watch_live(self.conn, settings, NOW, api=fake_api)
        self.assertIsNone(
            self.conn.execute("SELECT 1 FROM live_watch WHERE lot_id='atomic-lot'").fetchone()
        )
        self.assertIsNone(fetch_lot_image(self.conn, "atomic-lot"))

    def test_telegram_acceptance_before_db_commit_is_at_least_once(self) -> None:
        self._queue("duplicate-risk-lot", "https://source.invalid/duplicate-risk.jpg")
        transport = FakeTelegramTransport([self._fixture_result(), self._fixture_result()])
        with patch(
            "cuti.telegram_media.upload_image_to_telegram",
            side_effect=callback_transport(transport),
        ), patch(
            "cuti.telegram_media.mark_lot_image_ready",
            side_effect=StorageError("simulated DB commit failure"),
        ):
            with self.assertRaises(StorageError):
                process_lot_image_queue(self.conn, self.settings, NOW, worker_id="worker-a")
        self.assertEqual(len(transport.calls), 1)
        stuck = fetch_lot_image(self.conn, "duplicate-risk-lot")
        self.assertEqual(stuck["state"], "uploading")
        self.assertEqual(stuck["lease_owner"], "worker-a")
        with patch(
            "cuti.telegram_media.upload_image_to_telegram",
            side_effect=callback_transport(transport),
        ):
            process_lot_image_queue(
                self.conn,
                self.settings,
                NOW + timedelta(seconds=30),
                worker_id="worker-b",
            )
        self.assertEqual(len(transport.calls), 2)


if __name__ == "__main__":
    unittest.main()
