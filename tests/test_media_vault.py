"""Tests for Telegram media vault and lot images storage."""

from __future__ import annotations

import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from cuti.api import ApiError, get, write
from cuti.config import load_settings
from cuti.storage import LiveWatchRow, count_lot_images, fetch_lot_images, upsert_live_watch, upsert_lot_image
from cuti.telegram_media import format_lot_images, upload_image_to_telegram, upload_lot_images


class MediaVaultStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        from cuti.storage.schema_ddl import SCHEMA_SQL
        self.conn.executescript(SCHEMA_SQL)
        self.settings = load_settings(base_dir=Path(__file__).resolve().parents[1])

    def tearDown(self) -> None:
        self.conn.close()

    def test_upsert_and_fetch_lot_images(self) -> None:
        now = datetime.now(timezone.utc)
        upsert_lot_image(
            self.conn,
            lot_id="cw-100",
            idx=0,
            source_url="https://example.com/img0.jpg",
            telegram_file_id="tg_123",
            telegram_file_path="photos/file_0.jpg",
            telegram_message_id=42,
            uploaded_at=now,
        )
        upsert_lot_image(
            self.conn,
            lot_id="cw-100",
            idx=1,
            source_url="https://example.com/img1.jpg",
        )
        self.conn.commit()

        images = fetch_lot_images(self.conn, "cw-100")
        self.assertEqual(len(images), 2)
        self.assertEqual(images[0]["idx"], 0)
        self.assertEqual(images[0]["telegram_file_id"], "tg_123")
        self.assertEqual(images[0]["telegram_file_path"], "photos/file_0.jpg")
        self.assertEqual(images[1]["idx"], 1)
        self.assertIsNone(images[1]["telegram_file_id"])

        counts = count_lot_images(self.conn)
        self.assertEqual(counts["total"], 2)
        self.assertEqual(counts["uploaded"], 1)

    def test_format_lot_images_uses_same_origin_ready_url(self) -> None:
        images = [
            {
                "lot_id": "cw-100",
                "idx": 0,
                "source_url": "https://example.com/img0.jpg",
                "telegram_file_id": "tg_123",
                "telegram_file_path": "photos/file_0.jpg",
                "uploaded_at": "2026-08-26T00:00:00Z",
            },
            {
                "lot_id": "cw-100",
                "idx": 1,
                "source_url": "https://example.com/img1.jpg",
                "telegram_file_id": None,
                "telegram_file_path": None,
                "uploaded_at": None,
            },
        ]
        formatted = format_lot_images(images, self.settings)
        self.assertEqual(len(formatted), 2)
        self.assertEqual(formatted[0]["state"], "ready")
        self.assertEqual(formatted[0]["direct_url"], "/api/media/lots/cw-100/cover")
        self.assertEqual(formatted[0]["url"], "/api/media/lots/cw-100/cover")
        self.assertIsNone(formatted[0]["source_url"])
        self.assertNotIn("api.telegram.org", formatted[0]["direct_url"])
        self.assertNotIn("/bot", formatted[0]["direct_url"])
        self.assertEqual(formatted[1]["state"], "queued")
        self.assertIsNone(formatted[1]["direct_url"])
        self.assertIsNone(formatted[1]["url"])
        self.assertEqual(formatted[1]["source_url"], "https://example.com/img1.jpg")

    def test_api_get_and_post_lot_images(self) -> None:
        status, payload = get(self.conn, self.settings, "/api/lots/cw-100/images", {})
        self.assertEqual(status, 200)
        self.assertEqual(payload["images"], [])
        upsert_live_watch(
            self.conn,
            [LiveWatchRow("cw-100", "catawiki", "Test watch", None, "https://example.com/l/100", None)],
            datetime(2026, 8, 26, tzinfo=timezone.utc),
        )

        with patch("cuti.telegram_media.upload_image_to_telegram") as mock_upload:
            write_status, write_payload = write(
                self.conn,
                self.settings,
                "POST",
                "/api/lots/cw-100/images",
                {"image_urls": ["https://example.com/a.jpg"]},
            )
        mock_upload.assert_not_called()
        self.assertEqual(write_status, 200)
        self.assertEqual(write_payload["state"], "queued")
        self.assertEqual(write_payload["queued_count"], 1)
        self.assertEqual(len(write_payload["images"]), 1)
        self.assertEqual(write_payload["images"][0]["state"], "queued")
        self.assertIsNone(write_payload["images"][0]["direct_url"])
        self.assertEqual(write_payload["images"][0]["source_url"], "https://example.com/a.jpg")

        with self.assertRaises(ApiError) as raised:
            write(
                self.conn,
                self.settings,
                "POST",
                "/api/lots/cw-100/images",
                {"image_urls": ["https://example.com/a.jpg", "https://example.com/b.jpg"]},
            )
        self.assertEqual(raised.exception.status, 400)
        self.assertEqual(raised.exception.code, "invalid_cover_count")
        mock_upload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
