"""Tests for auction lots API with settled status and detail lookups."""

from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from cuti.api import get
from cuti.config import load_settings
from cuti.storage.schema_ddl import SCHEMA_SQL


class AuctionSettledApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.settings = load_settings(base_dir=Path(__file__).resolve().parents[1])

        # Insert a settled lot into lots
        self.conn.execute(
            """
            INSERT INTO lots (
                lot_id, source, title, brand, model_key, condition_tag, form,
                hearts, sold, hammer_eur, opened_at, ended_at, url, subtitle,
                bids_count, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "settled-001",
                "catawiki",
                "Seiko Spirit Chronograph 8T63",
                "seiko",
                "seiko:spirit",
                "naked",
                "round",
                20,
                1,
                90,
                "2026-08-20",
                "2026-08-26",
                "https://example.com/l/settled-001",
                "Quartz - Steel",
                30,
                "2026-08-26T12:00:00Z",
            ),
        )
        # Insert a live lot into live_watch
        self.conn.execute(
            """
            INSERT INTO live_watch (lot_id, source, title, subtitle, url, bidding_end_at, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "live-001",
                "catawiki",
                "Omega Seamaster Diver 300M",
                "Automatic",
                "https://example.com/l/live-001",
                "2026-09-10T18:00:00Z",
                "2026-09-07T00:00:00Z",
                "2026-09-07T00:00:00Z",
            ),
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_query_settled_lots(self) -> None:
        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"]})
        self.assertEqual(status, 200)
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(len(payload["lots"]), 1)
        lot = payload["lots"][0]
        self.assertEqual(lot["lot_id"], "settled-001")
        self.assertEqual(lot["status"], "settled")
        self.assertEqual(lot["hammer_eur"], 90)
        self.assertTrue(lot["sold"])
        self.assertEqual(lot["bids_count"], 30)
        self.assertEqual(lot["hearts"], 20)

    def test_query_settled_lots_with_search(self) -> None:
        status, payload = get(
            self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["Spirit"]}
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["lots"]), 1)

        status, empty_payload = get(
            self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["Omega"]}
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(empty_payload["lots"]), 0)

    def test_get_settled_lot_detail(self) -> None:
        status, payload = get(self.conn, self.settings, "/api/auction-lots/settled-001", {})
        self.assertEqual(status, 200)
        lot = payload["lot"]
        self.assertEqual(lot["lot_id"], "settled-001")
        self.assertEqual(lot["status"], "settled")
        self.assertEqual(lot["hammer_eur"], 90)
        self.assertTrue(lot["sold"])

    def test_query_unsold_and_unclassified_settled_lots(self) -> None:
        import json
        self.conn.execute(
            """
            INSERT INTO lots (
                lot_id, source, title, brand, model_key, condition_tag, form,
                hearts, sold, hammer_eur, opened_at, ended_at, url, subtitle,
                bids_count, needs_review, specs_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "settled-unsold-002",
                "catawiki",
                "Tissot Automatics III Day Date 2010-2020",
                "tissot",
                "tissot:unclassified",
                "naked",
                "unknown",
                18,
                0,
                None,
                "2026-08-20",
                "2026-08-29",
                "https://example.com/l/settled-unsold-002",
                "Men",
                11,
                1,
                json.dumps({"unclassified_reason": "title states no condition", "highest_bid_eur": 250.0}),
                "2026-08-29T20:00:00Z",
            ),
        )
        self.conn.commit()
        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["Tissot"]})
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["lots"]), 1)
        lot = payload["lots"][0]
        self.assertEqual(lot["lot_id"], "settled-unsold-002")
        self.assertFalse(lot["sold"])
        self.assertIsNone(lot["hammer_eur"])
        self.assertEqual(lot["highest_bid_eur"], 250.0)
        self.assertEqual(lot["needs_review"], 1)
        self.assertEqual(lot["unclassified_reason"], "title states no condition")

        status, detail_payload = get(self.conn, self.settings, "/api/auction-lots/settled-unsold-002", {})
        self.assertEqual(status, 200)
        detail_lot = detail_payload["lot"]
        self.assertEqual(detail_lot["lot_id"], "settled-unsold-002")
        self.assertFalse(detail_lot["sold"])
        self.assertEqual(detail_lot["highest_bid_eur"], 250.0)
        self.assertEqual(detail_lot["needs_review"], 1)
        self.assertEqual(detail_lot["unclassified_reason"], "title states no condition")

    def test_query_cancelled_settled_lot(self) -> None:
        import json

        self.conn.execute(
            """
            INSERT INTO lots (
                lot_id, source, title, brand, model_key, condition_tag, form,
                hearts, sold, hammer_eur, opened_at, ended_at, url, subtitle,
                bids_count, needs_review, source_available, review_status, specs_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "settled-cancelled-003",
                "catawiki",
                "Ulysse Nardin - Freak Diavolo Rolf 75",
                "ulysse nardin",
                "ulysse nardin:unclassified",
                "naked",
                "unknown",
                3,
                0,
                None,
                "2026-08-20",
                "2026-08-30",
                "https://example.com/l/settled-cancelled-003",
                "Gold",
                0,
                0,
                "__NO__",
                "ignored",
                json.dumps(
                    {
                        "unclassified_reason": "lot_removed_by_source (HTTP 404)"
                    }
                ),
                "2026-08-30T20:00:00Z",
            ),
        )
        self.conn.commit()
        status, payload = get(
            self.conn,
            self.settings,
            "/api/auction-lots",
            {"status": ["settled"], "q": ["Freak"]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["lots"]), 1)
        lot = payload["lots"][0]
        self.assertEqual(lot["lot_id"], "settled-cancelled-003")
        self.assertFalse(lot["source_available"])
        self.assertEqual(lot["review_status"], "ignored")
        self.assertEqual(
            lot["unclassified_reason"], "lot_removed_by_source (HTTP 404)"
        )

        status, detail_payload = get(
            self.conn, self.settings, "/api/auction-lots/settled-cancelled-003", {}
        )
        self.assertEqual(status, 200)
        detail_lot = detail_payload["lot"]
        self.assertFalse(detail_lot["source_available"])
        self.assertEqual(detail_lot["review_status"], "ignored")


if __name__ == "__main__":
    unittest.main()

