"""Settlement adapter coverage for lot-page Details and descriptions."""

from __future__ import annotations

import json
import tempfile
import unittest
import zlib
from datetime import date, datetime, timezone
from pathlib import Path

from support import settings_for

from cuti import storage
from cuti.normalize import load_rules
from cuti.pipeline.settlement import persist, settle
from cuti.scrapers import catawiki_api as api


class _ClosedApi:
    def live_states(self, lot_ids: tuple[str, ...]) -> dict[str, api.LiveState]:
        return {
            "1": api.LiveState(
                "1", True, 4, date(2026, 8, 1), date(2026, 8, 10), None
            )
        }

    def outcome(self, lot_id: str) -> api.BiddingOutcome:
        return api.BiddingOutcome(lot_id, True, True, 1000, 5)


class SettlementDetailsTests(unittest.TestCase):
    def test_fake_page_is_resolved_and_description_is_compressed(self) -> None:
        root = Path(tempfile.mkdtemp())
        settings = settings_for(
            root,
            CUTI_RULES_PATH=str(Path(__file__).parents[1] / "config" / "rules.json"),
        )
        rules = load_rules(settings.rules_path)
        row = storage.LiveWatchRow(
            "1", "catawiki", "Rolex Submariner 116610LN - full set", None,
            "https://example.invalid/l/1", date(2026, 8, 1),
        )
        html = (
            "<table><tr><th>Brand</th><td>Rolex</td></tr>"
            "<tr><th>Model</th><td>Submariner</td></tr>"
            "<tr><th>Reference number</th><td>116610LN</td></tr>"
            "<tr><th>Movement</th><td>Chronograph</td></tr></table>"
            '<section class="description"><p>Signed dial and steel bracelet.</p></section>'
        )
        settlement = settle(
            _ClosedApi(), rules, settings, [row], fetch_details=lambda lot_id: html
        )
        with storage.connect(settings.db_path) as conn:
            persist(conn, settlement, datetime(2026, 8, 17, tzinfo=timezone.utc))
            stored = conn.execute(
                "SELECT model, case_code, movement, needs_review, specs_json "
                "FROM lots WHERE lot_id = '1'"
            ).fetchone()
            self.assertEqual(stored[0], "Submariner")
            self.assertEqual(stored[1], "116610LN")
            self.assertIsNone(stored[2])
            self.assertEqual(stored[3], 1)
            self.assertEqual(json.loads(stored[4])["model_key_tier"], 2)
            compressed = conn.execute(
                "SELECT desc_z FROM lot_desc WHERE lot_id = '1'"
            ).fetchone()[0]
            self.assertEqual(
                zlib.decompress(compressed).decode("utf-8"),
                "Signed dial and steel bracelet.",
            )


if __name__ == "__main__":
    unittest.main()
