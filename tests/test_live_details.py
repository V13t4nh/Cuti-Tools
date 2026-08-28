"""Offline coverage for the opt-in, rate-limited Catawiki Details path."""

from __future__ import annotations

import json
import tempfile
import urllib.error
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from cuti.errors import FetchError
from cuti.pipeline.details import build_lot_url
from cuti.pipeline.report import _lot_page_fetcher
from cuti.pipeline.settlement import persist, settle
from cuti.scrapers import catawiki_api as api
from cuti import storage
from cuti.normalize import load_rules

from support import settings_for


class _ClosedApi:
    def live_states(self, lot_ids: tuple[str, ...]) -> dict[str, api.LiveState]:
        return {"1": api.LiveState("1", True, 4, date(2026, 8, 1), date(2026, 8, 10), None)}

    def outcome(self, lot_id: str) -> api.BiddingOutcome:
        return api.BiddingOutcome(lot_id, True, True, 1000, 5)


class DetailsPathTests(unittest.TestCase):
    def setUp(self) -> None:
        import shutil

        self.root = Path(tempfile.mkdtemp())
        (self.root / "config").mkdir()
        shutil.copy(Path(__file__).parents[1] / "config" / "rules.json", self.root / "config" / "rules.json")
        self.settings = settings_for(
            self.root,
            CUTI_RULES_PATH=str(Path(__file__).parents[1] / "config" / "rules.json"),
        )
        self.row = storage.LiveWatchRow(
            "1", "catawiki", "Rolex Submariner 116610LN - full set", None,
            "https://old.example/l/1", date(2026, 8, 1),
        )

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def test_builds_one_canonical_lot_url(self) -> None:
        self.assertEqual(build_lot_url("https://www.catawiki.com/", "123"), "https://www.catawiki.com/en/l/123")

    def test_disabled_fetcher_never_calls_transport(self) -> None:
        fetcher = _lot_page_fetcher([self.row], self.settings)
        with patch("cuti.pipeline.report.fetch_text") as transport:
            self.assertIsNone(fetcher("1"))
            transport.assert_not_called()

    def test_temporary_failures_retry_with_exponential_backoff(self) -> None:
        settings = settings_for(self.root, CUTI_DETAILS_ENABLED="true")
        fetcher = _lot_page_fetcher([self.row], settings)
        attempts = 0

        def fake_fetch(url: str, timeout: float, max_bytes: int) -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                cause = urllib.error.HTTPError(url, 503, "temporary", {}, None)
                raise FetchError("temporary details failure") from cause
            return "<html>ok</html>"

        with patch("cuti.pipeline.report.fetch_text", side_effect=fake_fetch), patch(
            "cuti.pipeline.report.time.sleep"
        ) as sleeper:
            self.assertEqual(fetcher("1"), "<html>ok</html>")
        self.assertEqual(attempts, 3)
        self.assertEqual([call.args[0] for call in sleeper.call_args_list], [1.0, 2.0])

    def test_enabled_details_resolve_fields_and_description(self) -> None:
        settings = settings_for(self.root, CUTI_DETAILS_ENABLED="true")
        rules = load_rules(settings.rules_path)
        html = (
            "<table><tr><th>Brand</th><td>Rolex</td></tr>"
            "<tr><th>Model</th><td>Submariner</td></tr>"
            "<tr><th>Reference number</th><td>116610LN</td></tr></table>"
            '<section class="description"><p>Signed dial.</p></section>'
        )
        fetcher = _lot_page_fetcher([self.row], settings)
        with patch("cuti.pipeline.report.fetch_text", return_value=html):
            settlement = settle(_ClosedApi(), rules, settings, [self.row], fetch_details=fetcher)
        with storage.connect(settings.db_path) as conn:
            persist(conn, settlement, datetime(2026, 8, 17, tzinfo=timezone.utc))
            stored = conn.execute("SELECT model, specs_json FROM lots WHERE lot_id='1'").fetchone()
            self.assertEqual(stored[0], "Submariner")
            self.assertEqual(json.loads(stored[1])["model_key_tier"], 2)
            self.assertIsNotNone(conn.execute("SELECT desc_z FROM lot_desc WHERE lot_id='1'").fetchone())

    def test_permanent_details_error_reports_failure_without_persisting_lot(self) -> None:
        settings = settings_for(self.root, CUTI_DETAILS_ENABLED="true")
        rules = load_rules(settings.rules_path)
        fetcher = _lot_page_fetcher([self.row], settings)
        cause = urllib.error.HTTPError(self.row.url, 404, "permanent", {}, None)
        def permanent_fetch(url: str, timeout: float, max_bytes: int) -> str:
            raise FetchError("permanent details failure") from cause

        with patch("cuti.pipeline.report.fetch_text", side_effect=permanent_fetch):
            settlement = settle(_ClosedApi(), rules, settings, [self.row], fetch_details=fetcher)
        self.assertEqual(settlement.details_failed, 1)
        self.assertEqual(settlement.errors, ["1: permanent details failure"])
        self.assertEqual(settlement.lots, [])
        with storage.connect(settings.db_path) as conn:
            now = datetime(2026, 8, 17, tzinfo=timezone.utc)
            storage.upsert_live_watch(conn, [self.row], now)
            written = persist(conn, settlement, now)
            self.assertEqual(written, 0)
            self.assertIsNone(conn.execute("SELECT model FROM lots WHERE lot_id='1'").fetchone())
            self.assertIsNone(conn.execute("SELECT desc_z FROM lot_desc WHERE lot_id='1'").fetchone())
            self.assertIsNotNone(conn.execute("SELECT 1 FROM live_watch WHERE lot_id='1'").fetchone())


if __name__ == "__main__":
    unittest.main()
