"""Unit tests for multi-image gallery extraction and self-healing reconciliation."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cuti.daily import reconcile_missing_lot_galleries
from cuti.pipeline.gallery import extract_lot_gallery, get_lot_gallery_images
from cuti.storage import (
    LiveWatchRow,
    connect,
    fetch_lot_images,
    find_lots_missing_gallery,
    upsert_live_watch,
    upsert_lot_gallery_images,
    upsert_lot_image,
    upsert_lots,
)
from daily_crawl_harness import block_network
from support import NOW, make_lot, settings_for

SAMPLE_NEXT_DATA_HTML = """
<!DOCTYPE html>
<html>
<head><title>Rolex Explorer II</title></head>
<body>
<div id="__next">Content</div>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "lotDetailsData": {
        "id": 106255624,
        "title": "Rolex - Explorer II - 16570 - Men - 2000-2010",
        "images": [
          {
            "large": "https://assets.catawiki.nl/assets/2026/2/23/a/1/photo_1.jpg",
            "medium": "https://assets.catawiki.nl/assets/2026/2/23/a/1/thumb5_photo_1.jpg",
            "thumbnail": "https://assets.catawiki.nl/assets/2026/2/23/a/1/thumb5_photo_1.jpg"
          },
          {
            "large": "https://assets.catawiki.nl/assets/2026/2/23/b/2/photo_2.jpg",
            "medium": "https://assets.catawiki.nl/assets/2026/2/23/b/2/thumb5_photo_2.jpg"
          },
          {
            "large": "https://assets.catawiki.nl/assets/2026/2/23/c/3/photo_3.jpg"
          }
        ]
      }
    }
  }
}
</script>
<div class="recommendations">
  <img src="https://assets.catawiki.nl/assets/2024/9/9/e/6/8/recommendation_photo.jpg" />
</div>
</body>
</html>
"""

SAMPLE_RAW_REGEX_HTML = """
<html>
<body>
  <img src="https://assets.catawiki.nl/assets/2026/1/1/x/thumb5_img1.jpg" />
  <img src="https://assets.catawiki.nl/assets/2026/1/1/y/img2.jpg" />
  <img src="https://assets.catawiki.nl/assets/2026/buyer/icon.png" />
  <img src="https://assets.catawiki.nl/assets/categories/watches.jpg" />
</body>
</html>
"""


class GalleryReconcileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="cuti-test-gallery-"))
        self.addCleanup(self._cleanup)
        self.conn = connect(self.temp_dir / "isolated.db")
        self.settings = settings_for(
            self.temp_dir,
            CUTI_DETAILS_REQUEST_DELAY_SECONDS="0.01",
            CUTI_NOTIFIER="file",
        )
        self.network_guard = block_network()
        self.network_guard.__enter__()
        self.addCleanup(self.network_guard.__exit__, None, None, None)

    def _cleanup(self) -> None:
        import shutil

        try:
            self.conn.close()
        except Exception:
            pass
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_lot_gallery_from_next_data(self) -> None:
        urls = extract_lot_gallery(SAMPLE_NEXT_DATA_HTML)
        self.assertEqual(len(urls), 3)
        self.assertEqual(urls[0], "https://assets.catawiki.nl/assets/2026/2/23/a/1/photo_1.jpg")
        self.assertEqual(urls[1], "https://assets.catawiki.nl/assets/2026/2/23/b/2/photo_2.jpg")
        self.assertEqual(urls[2], "https://assets.catawiki.nl/assets/2026/2/23/c/3/photo_3.jpg")
        self.assertNotIn("thumb", urls[0])
        self.assertNotIn("recommendation_photo.jpg", [u for u in urls])

    def test_extract_lot_gallery_fallback_regex(self) -> None:
        urls = extract_lot_gallery(SAMPLE_RAW_REGEX_HTML)
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0], "https://assets.catawiki.nl/assets/2026/1/1/x/img1.jpg")
        self.assertEqual(urls[1], "https://assets.catawiki.nl/assets/2026/1/1/y/img2.jpg")
        for u in urls:
            self.assertNotIn("/buyer/", u)
            self.assertNotIn("/categories/", u)

    def test_upsert_and_find_missing_gallery(self) -> None:
        upsert_live_watch(
            self.conn,
            [LiveWatchRow("cw-1", "catawiki", "Watch 1", None, "https://example.com/l/1", None)],
            NOW,
        )
        # Initially cw-1 has no gallery
        candidates = find_lots_missing_gallery(self.conn)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][0], "cw-1")

        # Upsert cover image (idx = 0) - still missing gallery (idx >= 1)
        upsert_lot_image(self.conn, lot_id="cw-1", idx=0, source_url="https://example.com/cover.jpg")
        candidates = find_lots_missing_gallery(self.conn)
        self.assertEqual(len(candidates), 1)

        # Upsert 2 gallery images
        count = upsert_lot_gallery_images(
            self.conn,
            "cw-1",
            ["https://assets.catawiki.nl/img1.jpg", "https://assets.catawiki.nl/img2.jpg"],
        )
        self.assertEqual(count, 2)

        # Now lot is no longer missing gallery
        candidates_after = find_lots_missing_gallery(self.conn)
        self.assertEqual(len(candidates_after), 0)

        # Stored records should have 3 images total: idx 0 (queued/ready) and idx 1, 2 (ready)
        all_imgs = fetch_lot_images(self.conn, "cw-1")
        self.assertEqual(len(all_imgs), 3)
        self.assertEqual(all_imgs[0]["idx"], 0)
        self.assertEqual(all_imgs[1]["idx"], 1)
        self.assertEqual(all_imgs[1]["state"], "ready")
        self.assertEqual(all_imgs[2]["idx"], 2)
        self.assertEqual(all_imgs[2]["state"], "ready")

        # Upserting fewer images should prune stale indices
        upsert_lot_gallery_images(
            self.conn,
            "cw-1",
            ["https://assets.catawiki.nl/img_only_one.jpg"],
        )
        pruned_imgs = fetch_lot_images(self.conn, "cw-1")
        self.assertEqual(len(pruned_imgs), 2)  # idx 0 cover + idx 1
        self.assertEqual(pruned_imgs[1]["source_url"], "https://assets.catawiki.nl/img_only_one.jpg")

    def test_reconcile_missing_lot_galleries_workflow(self) -> None:
        upsert_live_watch(
            self.conn,
            [
                LiveWatchRow("cw-10", "catawiki", "Watch 10", None, "https://example.com/l/10", None),
                LiveWatchRow("cw-20", "ebay", "Watch 20", None, "https://example.com/l/20", None),
            ],
            NOW,
        )
        sleep_calls: list[float] = []

        def mock_fetch(url: str, **kwargs: object) -> str:
            del kwargs
            if "l/10" in url:
                return SAMPLE_NEXT_DATA_HTML
            raise RuntimeError(f"Unexpected url {url}")

        report = reconcile_missing_lot_galleries(
            self.conn,
            self.settings,
            NOW,
            fetch_text_fn=mock_fetch,
            sleep_fn=sleep_calls.append,
        )

        self.assertEqual(report.candidates, 2)
        self.assertEqual(report.resolved, 1)
        self.assertEqual(report.images_stored, 3)
        self.assertEqual(len(report.failures), 1)
        self.assertIn("unsupported gallery source 'ebay'", report.failures[0])

        # Verify images populated in db
        imgs = fetch_lot_images(self.conn, "cw-10")
        self.assertEqual(len(imgs), 3)
        self.assertEqual(imgs[0]["idx"], 1)
        self.assertEqual(imgs[0]["source_url"], "https://assets.catawiki.nl/assets/2026/2/23/a/1/photo_1.jpg")

    def test_get_lot_gallery_images_api_integration(self) -> None:
        upsert_live_watch(
            self.conn,
            [LiveWatchRow("cw-30", "catawiki", "Watch 30", None, "https://example.com/l/30", None)],
            NOW,
        )
        upsert_lot_image(
            self.conn,
            lot_id="cw-30",
            idx=0,
            source_url="https://assets.catawiki.nl/cover.jpg",
            telegram_file_id="tg-cover",
        )

        # Pre-populate gallery
        upsert_lot_gallery_images(
            self.conn,
            "cw-30",
            ["https://assets.catawiki.nl/img1.jpg", "https://assets.catawiki.nl/img2.jpg"],
        )

        formatted = get_lot_gallery_images(self.conn, "cw-30", self.settings)
        self.assertEqual(len(formatted), 3)
        self.assertEqual(formatted[0]["idx"], 0)
        self.assertEqual(formatted[0]["url"], "/api/media/lots/cw-30/cover")
        self.assertEqual(formatted[1]["idx"], 1)
        self.assertEqual(formatted[1]["url"], "https://assets.catawiki.nl/img1.jpg")
        self.assertEqual(formatted[1]["direct_url"], "https://assets.catawiki.nl/img1.jpg")
        self.assertEqual(formatted[1]["state"], "ready")


if __name__ == "__main__":
    unittest.main()
