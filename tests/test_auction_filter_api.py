"""Tests for auction-lots API filtering by conditions and qualities."""

from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path

from cuti.api import get
from cuti.config import load_settings
from cuti.storage.schema_ddl import SCHEMA_SQL


class AuctionFilterApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.settings = load_settings(base_dir=Path(__file__).resolve().parents[1])

        lots_data = [
            (
                "lot-001",
                "catawiki",
                "Rolex Submariner 16610",
                "rolex",
                "rolex:submariner",
                "fullset",
                "round",
                50,
                1,
                8500,
                "2026-08-01",
                "2026-08-10",
                "https://example.com/l/lot-001",
                json.dumps({"Condition": "New"}),
                json.dumps({"condition": {"case_condition": "unpolished"}}),
            ),
            (
                "lot-002",
                "catawiki",
                "Omega Speedmaster Professional",
                "omega",
                "omega:speedmaster",
                "box",
                "round",
                30,
                1,
                4200,
                "2026-08-05",
                "2026-08-12",
                "https://example.com/l/lot-002",
                json.dumps({"Condition": "Very good - minor signs of wear"}),
                None,
            ),
            (
                "lot-003",
                "catawiki",
                "Seiko SARB033 Automatic",
                "seiko",
                "seiko:sarb033",
                "naked",
                "round",
                15,
                1,
                550,
                "2026-08-10",
                "2026-08-15",
                "https://example.com/l/lot-003",
                json.dumps({"Condition": "Good - visible signs of wear"}),
                None,
            ),
            (
                "lot-004",
                "catawiki",
                "Longines Vintage Manual",
                "longines",
                "longines:vintage",
                "papers",
                "round",
                10,
                0,
                None,
                "2026-08-12",
                "2026-08-18",
                "https://example.com/l/lot-004",
                json.dumps({"Condition": "Fair - major signs of wear"}),
                json.dumps({"condition": {"case_condition": "dented"}}),
            ),
        ]

        for item in lots_data:
            self.conn.execute(
                """
                INSERT INTO lots (
                    lot_id, source, title, brand, model_key, condition_tag, form,
                    hearts, sold, hammer_eur, opened_at, ended_at, url, specs_json, ai_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '2026-08-20T12:00:00Z')
                """,
                item,
            )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_filter_by_single_condition(self) -> None:
        status, payload = get(
            self.conn,
            self.settings,
            "/api/auction-lots",
            {"status": ["settled"], "conditions": ["fullset"]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(payload["lots"][0]["lot_id"], "lot-001")
        self.assertEqual(payload["lots"][0]["condition_tag"], "fullset")
        self.assertEqual(payload["lots"][0]["quality"], "new_unworn")

    def test_filter_by_multi_conditions(self) -> None:
        status, payload = get(
            self.conn,
            self.settings,
            "/api/auction-lots",
            {"status": ["settled"], "conditions": ["fullset,box"]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["pagination"]["total"], 2)
        lot_ids = {lot["lot_id"] for lot in payload["lots"]}
        self.assertEqual(lot_ids, {"lot-001", "lot-002"})

    def test_filter_by_single_quality(self) -> None:
        status, payload = get(
            self.conn,
            self.settings,
            "/api/auction-lots",
            {"status": ["settled"], "qualities": ["very_good"]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(payload["lots"][0]["lot_id"], "lot-002")
        self.assertEqual(payload["lots"][0]["quality"], "very_good")

    def test_filter_by_multi_qualities(self) -> None:
        status, payload = get(
            self.conn,
            self.settings,
            "/api/auction-lots",
            {"status": ["settled"], "qualities": ["new_unworn,fair"]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["pagination"]["total"], 2)
        lot_ids = {lot["lot_id"] for lot in payload["lots"]}
        self.assertEqual(lot_ids, {"lot-001", "lot-004"})

    def test_combined_filter(self) -> None:
        status, payload = get(
            self.conn,
            self.settings,
            "/api/auction-lots",
            {"status": ["settled"], "conditions": ["naked,papers"], "qualities": ["good"]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(payload["lots"][0]["lot_id"], "lot-003")

    def test_detail_endpoint_returns_condition_and_quality(self) -> None:
        status, payload = get(self.conn, self.settings, "/api/auction-lots/lot-001", {})
        self.assertEqual(status, 200)
        lot = payload["lot"]
        self.assertEqual(lot["condition_tag"], "fullset")
        self.assertEqual(lot["quality"], "new_unworn")
