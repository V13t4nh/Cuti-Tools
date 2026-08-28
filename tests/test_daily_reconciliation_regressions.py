"""Offline regressions for exact cover lookup and missing-image recovery."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from cuti.daily import reconcile_missing_lot_images
from cuti.errors import FetchError, ScrapeError
from cuti.scrapers.catawiki_api import CatawikiApi
from cuti.storage import (
    connect,
    fetch_lot_image,
    upsert_live_watch,
    upsert_lots,
    LiveWatchRow,
)
from daily_crawl_harness import block_network
from support import NOW, make_lot, settings_for


FIXTURE = Path(__file__).parent / "fixtures" / "daily_crawl" / "cover_lookup.json"
LIVE_COVER_EXPECTED = Path(__file__).parent / "fixtures" / "daily_crawl" / "daily-source-payload-expected.json"
LIVE_COVER_PAYLOAD = Path(__file__).parent / "fixtures" / "daily_crawl" / "daily-source-payload-fixture.json"
DUPLICATE_CONFLICT = Path(__file__).parent / "fixtures" / "daily_crawl" / "catawiki-lots-duplicate-conflict.json"
DUPLICATE_EXACT = Path(__file__).parent / "fixtures" / "daily_crawl" / "catawiki-lots-duplicate-exact.json"


class FakeCoverApi:
    def __init__(self, mapping: dict[str, object], error: Exception | None = None) -> None:
        self.mapping = mapping
        self.error = error
        self.requests: list[tuple[str, ...]] = []

    def covers(self, lot_ids: tuple[str, ...]) -> dict[str, object]:
        ids = tuple(lot_ids)
        self.requests.append(ids)
        if self.error is not None:
            raise self.error
        return {lot_id: self.mapping.get(lot_id) for lot_id in ids}


class ReconciliationRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="cuti-daily-reconcile-"))
        self.addCleanup(self._cleanup)
        self.conn = connect(self.temp_dir / "isolated.db")
        self.settings = settings_for(
            self.temp_dir,
            CUTI_CATAWIKI_BATCH_SIZE="2",
            CUTI_CATAWIKI_PAUSE_SECONDS="0",
            CUTI_NOTIFIER="file",
        )
        self.network_guard = block_network()
        self.network_guard.__enter__()
        self.addCleanup(self.network_guard.__exit__, None, None, None)

    def _cleanup(self) -> None:
        self.conn.close()
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _live(self, lot_id: str, source: str = "catawiki") -> None:
        upsert_live_watch(
            self.conn,
            [LiveWatchRow(lot_id, source, lot_id, None, f"https://source.invalid/{lot_id}", None)],
            NOW,
        )

    def test_db_only_and_live_only_lots_resolve_from_exact_ids(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        upsert_lots(self.conn, [make_lot("db-only-lot"), make_lot("covered-lot")], NOW)
        self._live("live-only-lot")
        from cuti.storage import upsert_lot_image

        upsert_lot_image(
            self.conn,
            lot_id="covered-lot",
            idx=0,
            source_url="https://source.invalid/images/already-covered.jpg",
        )
        self.conn.commit()
        api = FakeCoverApi(fixture["resolved"])

        report = reconcile_missing_lot_images(self.conn, self.settings, NOW, api=api)

        self.assertEqual(report.candidates, 2)
        self.assertEqual(report.queued, 2)
        self.assertEqual(report.missing, ())
        self.assertEqual(report.failures, ())
        self.assertEqual(api.requests, [("db-only-lot", "live-only-lot")])
        self.assertEqual(
            fetch_lot_image(self.conn, "db-only-lot")["source_url"],
            fixture["resolved"]["db-only-lot"],
        )
        self.assertEqual(
            fetch_lot_image(self.conn, "live-only-lot")["source_url"],
            fixture["resolved"]["live-only-lot"],
        )
        self.assertIsNone(fetch_lot_image(self.conn, "covered-lot")["last_error"])

    def test_empty_source_cover_is_missing_without_a_guessed_url(self) -> None:
        upsert_lots(
            self.conn,
            [make_lot("empty-image-lot"), make_lot("missing-image-lot")],
            NOW,
        )
        api = FakeCoverApi({"empty-image-lot": None, "missing-image-lot": None})

        report = reconcile_missing_lot_images(self.conn, self.settings, NOW, api=api)

        self.assertEqual(report.candidates, 2)
        self.assertEqual(report.queued, 0)
        self.assertEqual(report.missing, ("empty-image-lot", "missing-image-lot"))
        self.assertEqual(report.failures, ())
        self.assertIsNone(fetch_lot_image(self.conn, "empty-image-lot"))
        self.assertIsNone(fetch_lot_image(self.conn, "missing-image-lot"))

    def test_typed_source_failure_is_reported_and_does_not_write_images(self) -> None:
        upsert_lots(self.conn, [make_lot("source-failed-lot")], NOW)
        api = FakeCoverApi({}, FetchError("source returned HTTP 503"))

        report = reconcile_missing_lot_images(self.conn, self.settings, NOW, api=api)

        self.assertEqual(report.candidates, 1)
        self.assertEqual(report.queued, 0)
        self.assertEqual(report.missing, ())
        self.assertEqual(report.failures, ("source-failed-lot: source returned HTTP 503",))
        self.assertIsNone(fetch_lot_image(self.conn, "source-failed-lot"))

    def test_invalid_cover_payload_is_failure_not_a_fallback(self) -> None:
        upsert_lots(self.conn, [make_lot("invalid-image-lot")], NOW)
        api = FakeCoverApi({"invalid-image-lot": 123})

        report = reconcile_missing_lot_images(self.conn, self.settings, NOW, api=api)

        self.assertEqual(report.queued, 0)
        self.assertEqual(report.missing, ())
        self.assertEqual(
            report.failures,
            ("invalid-image-lot: source returned an invalid cover URL",),
        )
        self.assertIsNone(fetch_lot_image(self.conn, "invalid-image-lot"))

    def test_unsupported_source_is_explicit_failure_and_not_queried(self) -> None:
        upsert_lots(self.conn, [make_lot("other-source-lot", source="other")], NOW)
        api = FakeCoverApi({})

        report = reconcile_missing_lot_images(self.conn, self.settings, NOW, api=api)

        self.assertEqual(report.candidates, 1)
        self.assertEqual(report.queued, 0)
        self.assertEqual(report.failures, ("other-source-lot: unsupported source 'other'",))
        self.assertEqual(api.requests, [])


class ExactCoverAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.network_guard = block_network()
        self.network_guard.__enter__()
        self.addCleanup(self.network_guard.__exit__, None, None, None)

    def _client(self, fetch: Any) -> CatawikiApi:
        return CatawikiApi(
            api_base="https://source.invalid",
            timeout_seconds=1,
            max_bytes=100_000,
            pause_seconds=0,
            fetch=fetch,
        )

    def test_covers_uses_exact_ids_and_returns_source_url_or_none(self) -> None:
        calls: list[str] = []

        def fetch(url: str, _timeout: float, _max_bytes: int) -> dict[str, object]:
            calls.append(url)
            return {
                "lots": [
                    {
                        "id": 101,
                        "title": "Lot 101",
                        "url": "https://source.invalid/en/l/101-lot",
                        "originalImageUrl": "https://images.invalid/101.jpg",
                    }
                ]
            }

        result = self._client(fetch).covers(["101", "202"])

        self.assertEqual(result, {"101": "https://images.invalid/101.jpg", "202": None})
        self.assertEqual(calls, ["https://source.invalid/buyer/api/v1/lots?ids=101,202"])

    def test_empty_source_response_returns_none_without_guessing(self) -> None:
        result = self._client(lambda *_args: {"lots": []}).covers(["101"])
        self.assertEqual(result, {"101": None})

    def test_invalid_cover_payload_is_typed_error(self) -> None:
        def fetch(*_args: object) -> dict[str, object]:
            return {
                "lots": [
                    {
                        "id": 101,
                        "title": "Lot 101",
                        "url": "https://source.invalid/en/l/101-lot",
                        "originalImageUrl": "not-a-url",
                    }
                ]
            }

        with self.assertRaises(ScrapeError):
            self._client(fetch).covers(["101"])

    def test_404_transport_failure_is_typed_error(self) -> None:
        def fetch(*_args: object) -> object:
            raise FetchError("source returned HTTP 404")

        with self.assertRaises(FetchError):
            self._client(fetch).covers(["101"])

    def test_saved_live_payload_parses_to_saved_normalized_cover_fixture(self) -> None:
        payload = json.loads(LIVE_COVER_PAYLOAD.read_text(encoding="utf-8"))
        expected = json.loads(LIVE_COVER_EXPECTED.read_text(encoding="utf-8"))
        ids = [str(item["id"]) for item in payload["lots"]]

        result = self._client(lambda *_args: payload).covers(ids)

        self.assertEqual(
            result,
            {item["lot_id"]: item["cover_url"] for item in expected},
        )

    def test_duplicate_lot_records_with_conflicting_covers_are_typed_failure(self) -> None:
        payload = json.loads(DUPLICATE_CONFLICT.read_text(encoding="utf-8"))

        with self.assertRaises(ScrapeError):
            self._client(lambda *_args: payload).covers(["102916138"])

    def test_exact_duplicate_lot_records_have_one_consistent_cover(self) -> None:
        payload = json.loads(DUPLICATE_EXACT.read_text(encoding="utf-8"))

        result = self._client(lambda *_args: payload).covers(["102944656"])

        self.assertEqual(result, {"102944656": "https://assets.invalid/102944656-cover.jpg"})

if __name__ == "__main__":
    unittest.main()
