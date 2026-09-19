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

    def test_query_settled_lots_with_hyphens_and_word_tokens(self) -> None:
        self.conn.execute(
            """
            INSERT INTO lots (
                lot_id, source, title, brand, model_key, condition_tag, form,
                hearts, sold, hammer_eur, opened_at, ended_at, url, subtitle,
                bids_count, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "settled-003",
                "catawiki",
                "Seiko - King Seiko - 5626-7113 - Men - 1970-1979",
                "seiko",
                "seiko:king-seiko",
                "naked",
                "round",
                10,
                1,
                350,
                "2026-08-20",
                "2026-08-26",
                "https://example.com/l/settled-003",
                "Vintage",
                15,
                "2026-08-26T12:00:00Z",
            ),
        )
        self.conn.commit()

        for q in ["seiko king", "seiko - king", "seiko-king", "seiko 5626", "5626-7113"]:
            status, payload = get(
                self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": [q]}
            )
            self.assertEqual(status, 200)
            lot_ids = [l["lot_id"] for l in payload["lots"]]
            self.assertIn("settled-003", lot_ids, f"Failed to match query {q!r}")

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

    def test_query_open_lot_with_refinement_enrichment(self) -> None:
        import json
        self.conn.execute(
            """
            INSERT INTO live_watch (lot_id, source, title, subtitle, url, bidding_end_at, first_seen_at, last_seen_at)
            VALUES ('live-enriched-01', 'catawiki', 'Tecnotempo Automatic Chronograph', 'TelemetriX', 'https://example.com/live', '2099-01-01T00:00:00Z', '2026-09-18T00:00:00Z', '2026-09-18T00:00:00Z')
            """
        )
        self.conn.execute(
            """
            INSERT INTO lot_refinements (lot_id, source_hash, ai_json, refined_at, state, last_error)
            VALUES ('live-enriched-01', 'hash123', ?, '2026-09-18T12:00:00Z', 'ready', NULL)
            """,
            (json.dumps({
                "brand": "Tecnotempo",
                "model": "TelemetriX",
                "movement": "auto",
                "case_material": "steel",
                "case_diameter_mm": 40,
                "accessories": {"true_condition_tag": "fullset"},
            }),)
        )
        self.conn.commit()

        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["open"], "q": ["Tecnotempo"]})
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["lots"]), 1)
        lot = payload["lots"][0]
        self.assertEqual(lot["lot_id"], "live-enriched-01")
        self.assertEqual(lot["status"], "open")
        self.assertEqual(lot["condition_tag"], "fullset")
        self.assertEqual(lot["movement"], "auto")
        self.assertEqual(lot["case_material"], "steel")
        self.assertEqual(lot["case_diameter_mm"], 40)

        status, detail = get(self.conn, self.settings, "/api/auction-lots/live-enriched-01", {})
        self.assertEqual(status, 200)
        self.assertEqual(detail["lot"]["condition_tag"], "fullset")
        self.assertEqual(detail["lot"]["movement"], "auto")

    def test_search_compound_words_and_typo_fallback(self) -> None:
        self.conn.execute(
            """
            INSERT INTO lots (lot_id, source, title, brand, model, model_key, condition_tag, form, hearts, sold, hammer_eur, opened_at, ended_at, url, subtitle, bids_count, updated_at)
            VALUES
            ('lot-airking', 'catawiki', 'Rolex - Oyster Perpetual Air-King Precision', 'rolex', 'Air-King', 'rolex:air-king', 'naked', 'round', 15, 1, 2800, '2026-08-01', '2026-08-10', 'https://ex.com/ak', 'Automatic - Steel', 12, '2026-08-10T00:00:00Z'),
            ('lot-king-seiko', 'catawiki', 'Seiko - King Seiko Hi-Beat 5626', 'seiko', 'King Seiko', 'seiko:king-seiko', 'box', 'round', 25, 1, 450, '2026-08-01', '2026-08-10', 'https://ex.com/ks', 'Automatic - Steel', 20, '2026-08-10T00:00:00Z'),
            ('lot-seiko-chrono', 'catawiki', 'Seiko - Chronograph Quartz 8T63', 'seiko', 'Chronograph', 'seiko:chronograph', 'box', 'round', 18, 1, 150, '2026-08-01', '2026-08-10', 'https://ex.com/sc', 'Quartz - Steel', 15, '2026-08-10T00:00:00Z'),
            ('lot-talking', 'catawiki', 'Seiko Talking Watch Vintage', 'seiko', 'Talking Watch', 'seiko:talking-watch', 'naked', 'round', 5, 1, 60, '2026-08-01', '2026-08-10', 'https://ex.com/tw', 'Quartz - Plastic', 4, '2026-08-10T00:00:00Z')
            """
        )
        self.conn.commit()

        # 1. Compound search: 'airking' should match 'Air-King'
        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["airking"]})
        self.assertEqual(status, 200)
        lot_ids = [l["lot_id"] for l in payload["lots"]]
        self.assertIn("lot-airking", lot_ids)

        # 2. Hyphen search: 'air-king' should also match
        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["air-king"]})
        self.assertEqual(status, 200)
        lot_ids = [l["lot_id"] for l in payload["lots"]]
        self.assertIn("lot-airking", lot_ids)

        # 3. Typo fallback: 'rolexx' should match 'rolex'
        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["rolexx"]})
        self.assertEqual(status, 200)
        lot_ids = [l["lot_id"] for l in payload["lots"]]
        self.assertIn("lot-airking", lot_ids)

        # 4. Typo fallback: 'seikoo' should match 'seiko'
        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["seikoo"]})
        self.assertEqual(status, 200)
        lot_ids = [l["lot_id"] for l in payload["lots"]]
        self.assertIn("lot-king-seiko", lot_ids)
        self.assertIn("settled-001", lot_ids)

        # 5. Word boundary query: 'king' matches King Seiko and Air-King, but NOT Talking Watch
        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["king"]})
        self.assertEqual(status, 200)
        lot_ids = [l["lot_id"] for l in payload["lots"]]
        self.assertIn("lot-king-seiko", lot_ids)
        self.assertIn("lot-airking", lot_ids)
        self.assertNotIn("lot-talking", lot_ids)

        # 6. Intact vocab query: 'Seiko Chronograph' should not split 'chronograph' into 'chrono' + 'graph'
        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["Seiko Chronograph"]})
        self.assertEqual(status, 200)
        lot_ids = [l["lot_id"] for l in payload["lots"]]
        self.assertIn("lot-seiko-chrono", lot_ids)

    def test_case_diameter_and_numeral_search(self) -> None:
        self.conn.execute(
            """
            INSERT INTO lots (lot_id, source, title, brand, model, model_key, condition_tag, form, hearts, sold, hammer_eur, opened_at, ended_at, url, subtitle, bids_count, case_diameter_mm, updated_at)
            VALUES
            ('lot-dj36', 'catawiki', 'Rolex - Datejust 36 - Ref 16233', 'rolex', 'Datejust', 'rolex:datejust', 'box', 'round', 10, 1, 4200, '2026-08-01', '2026-08-10', 'https://ex.com/dj36', 'Automatic - Steel', 12, 36, '2026-08-10T00:00:00Z'),
            ('lot-sub40', 'catawiki', 'Rolex - Submariner - Ref 16610', 'rolex', 'Submariner', 'rolex:submariner', 'box', 'round', 15, 1, 7500, '2026-08-01', '2026-08-10', 'https://ex.com/sub40', 'Automatic - Steel', 18, 40, '2026-08-10T00:00:00Z'),
            ('lot-tissot-iii', 'catawiki', 'Tissot - Automatics III Day Date', 'tissot', 'Automatics III', 'tissot:automatics-iii', 'naked', 'round', 8, 1, 200, '2026-08-01', '2026-08-10', 'https://ex.com/t3', 'Automatic - Steel', 5, 39, '2026-08-10T00:00:00Z'),
            ('lot-iwc-18', 'catawiki', 'IWC - Pilot Mark XVIII Spitfire', 'iwc', 'Mark XVIII', 'iwc:mark-xviii', 'box', 'round', 22, 1, 3100, '2026-08-01', '2026-08-10', 'https://ex.com/iwc18', 'Automatic - Steel', 14, 40, '2026-08-10T00:00:00Z'),
            ('lot-iwc-20', 'catawiki', 'IWC - Pilot watch mark 20', 'iwc', 'Mark 20', 'iwc:mark-20', 'box', 'round', 19, 1, 3800, '2026-08-01', '2026-08-10', 'https://ex.com/iwc20', 'Automatic - Steel', 10, 40, '2026-08-10T00:00:00Z')
            """
        )
        self.conn.commit()

        # Diameter 36mm & 36 mm search
        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["rolex 36mm"]})
        self.assertEqual(status, 200)
        lot_ids = [l["lot_id"] for l in payload["lots"]]
        self.assertIn("lot-dj36", lot_ids)
        self.assertNotIn("lot-sub40", lot_ids)

        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["rolex 36 mm"]})
        self.assertEqual(status, 200)
        lot_ids = [l["lot_id"] for l in payload["lots"]]
        self.assertIn("lot-dj36", lot_ids)
        self.assertNotIn("lot-sub40", lot_ids)

        # Roman <-> Arabic numeral search: Tissot 3 <-> Tissot III
        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["tissot 3"]})
        self.assertEqual(status, 200)
        lot_ids = [l["lot_id"] for l in payload["lots"]]
        self.assertIn("lot-tissot-iii", lot_ids)

        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["tissot iii"]})
        self.assertEqual(status, 200)
        lot_ids = [l["lot_id"] for l in payload["lots"]]
        self.assertIn("lot-tissot-iii", lot_ids)

        # Mark 18 <-> Mark XVIII
        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["mark 18"]})
        self.assertEqual(status, 200)
        lot_ids = [l["lot_id"] for l in payload["lots"]]
        self.assertIn("lot-iwc-18", lot_ids)

        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["mark xviii"]})
        self.assertEqual(status, 200)
        lot_ids = [l["lot_id"] for l in payload["lots"]]
        self.assertIn("lot-iwc-18", lot_ids)

        # Mark 20 <-> Mark XX
        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["mark xx"]})
        self.assertEqual(status, 200)
        lot_ids = [l["lot_id"] for l in payload["lots"]]
        self.assertIn("lot-iwc-20", lot_ids)

        status, payload = get(self.conn, self.settings, "/api/auction-lots", {"status": ["settled"], "q": ["mark 20"]})
        self.assertEqual(status, 200)
        lot_ids = [l["lot_id"] for l in payload["lots"]]
        self.assertIn("lot-iwc-20", lot_ids)


if __name__ == "__main__":
    unittest.main()


