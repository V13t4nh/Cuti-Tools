"""Storage: schema invariants, idempotent upserts, dedupe, FTS sync."""

from __future__ import annotations

import sqlite3
import unittest
from datetime import date

from cuti.errors import ScrapeError, StorageError
from cuti.models import Condition, Deal, Lot, WatchForm
from cuti.storage import (
    claim_pending_alerts,
    count_rows,
    ensure_catalog,
    fetch_quote_audit,
    fetch_product,
    fetch_lots_for_liquidity,
    fetch_sold_lots_since,
    fetch_unquoted_deals,
    insert_deal_if_new,
    insert_quote,
    load_catalog,
    mark_alert_sent,
    search_products,
    search_sold_lots,
    upsert_lots,
)

from support import NOW, ProjectTestCase, make_lot


class LotModelTests(unittest.TestCase):
    def test_sold_lot_requires_hammer(self) -> None:
        with self.assertRaises(ScrapeError):
            Lot(
                lot_id="x",
                source="catawiki",
                title="Omega",
                brand="omega",
                model_key="omega:x",
                condition_tag=Condition.NAKED,
                hearts=1,
                sold=True,
                hammer_eur=None,
                opened_at=date(2026, 1, 1),
                ended_at=date(2026, 1, 2),
                url="u",
            )

    def test_unsold_lot_must_not_have_hammer(self) -> None:
        with self.assertRaises(ScrapeError):
            Lot(
                lot_id="x",
                source="catawiki",
                title="Omega",
                brand="omega",
                model_key="omega:x",
                condition_tag=Condition.NAKED,
                hearts=1,
                sold=False,
                hammer_eur=100,
                opened_at=date(2026, 1, 1),
                ended_at=date(2026, 1, 2),
                url="u",
            )

    def test_end_before_open_is_rejected(self) -> None:
        with self.assertRaises(ScrapeError):
            make_lot("x", ended_at=date(2026, 1, 1), days_open=-5)

    def test_days_to_close(self) -> None:
        self.assertEqual(make_lot("x", ended_at=date(2026, 1, 11), days_open=10).days_to_close, 10)

    def test_same_day_lot_is_valid(self) -> None:
        self.assertEqual(make_lot("x", days_open=0).days_to_close, 0)


class StorageTests(ProjectTestCase):
    def test_upsert_is_idempotent(self) -> None:
        lot = make_lot("cw-1")
        self.seed_lots([lot, lot])
        self.seed_lots([lot])
        self.assertEqual(count_rows(self.conn, "lots"), 1)

    def test_upsert_updates_existing_row(self) -> None:
        self.seed_lots([make_lot("cw-1", hammer_eur=1000)])
        self.seed_lots([make_lot("cw-1", hammer_eur=2000)])
        rows = fetch_sold_lots_since(self.conn, Condition.NAKED, date(2020, 1, 1))
        self.assertEqual([row.hammer_eur for row in rows], [2000])

    def test_empty_upsert_writes_nothing(self) -> None:
        self.assertEqual(upsert_lots(self.conn, [], NOW), 0)

    def test_fts_index_follows_updates_and_deletes(self) -> None:
        self.seed_lots(
            [
                make_lot(
                    "cw-1",
                    title="Omega Seamaster 210.30.42 watch only",
                    model_key="omega:210.30.42",
                )
            ]
        )
        found = search_sold_lots(
            self.conn,
            fts_query='"210.30.42"',
            brand="omega",
            model_key="omega:210.30.42",
            condition_tag=Condition.NAKED,
            since=date(2020, 1, 1),
            limit=10,
        )
        self.assertEqual(len(found), 1)

        self.seed_lots(
            [
                make_lot(
                    "cw-1",
                    title="Rolex Submariner 124060 watch only",
                    model_key="rolex:124060",
                )
            ]
        )
        self.assertEqual(
            search_sold_lots(
                self.conn,
                fts_query='"210.30.42"',
                brand="omega",
                model_key="omega:210.30.42",
                condition_tag=Condition.NAKED,
                since=date(2020, 1, 1),
                limit=10,
            ),
            [],
        )

        self.conn.execute("DELETE FROM lots")
        self.assertEqual(
            search_sold_lots(
                self.conn,
                fts_query='"124060"',
                brand="rolex",
                model_key="rolex:124060",
                condition_tag=Condition.NAKED,
                since=date(2020, 1, 1),
                limit=10,
            ),
            [],
        )

    def test_search_excludes_unsold_and_out_of_window(self) -> None:
        self.seed_lots(
            [
                make_lot("sold-recent", ended_at=date(2026, 7, 1)),
                make_lot("sold-old", ended_at=date(2020, 1, 5)),
                make_lot("unsold", sold=False, ended_at=date(2026, 7, 1)),
            ]
        )
        found = search_sold_lots(
            self.conn,
            fts_query='"210.30.42" OR "omega"',
            brand="omega",
            model_key="omega:210.30.42",
            condition_tag=Condition.NAKED,
            since=date(2026, 1, 1),
            limit=10,
        )
        self.assertEqual([lot.lot_id for lot in found], ["sold-recent"])

    def test_search_rejects_non_positive_limit(self) -> None:
        with self.assertRaises(StorageError):
            search_sold_lots(
                self.conn,
                fts_query='"omega"',
                brand="omega",
                model_key=None,
                condition_tag=Condition.NAKED,
                since=date(2020, 1, 1),
                limit=0,
            )

    def test_deal_dedupe_returns_none_second_time(self) -> None:
        deal = Deal(
            source="fb",
            raw_title="Omega Seamaster 210.30.42 with box",
            ask_vnd=70_000_000,
            url="https://example.invalid/1",
            seen_at=date(2026, 8, 1),
            model_key="omega:210.30.42",
            condition_tag=Condition.BOX,
            dedupe_hash="hash-1",
        )
        first = insert_deal_if_new(self.conn, deal, NOW)
        second = insert_deal_if_new(self.conn, deal, NOW)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(count_rows(self.conn, "deals"), 1)

    def test_unquoted_deal_query_filters_freshness_in_sql(self) -> None:
        old = Deal(
            source="fb",
            raw_title="Omega Seamaster 210.30.42 with box",
            ask_vnd=70_000_000,
            url="https://example.invalid/old",
            seen_at=date(2025, 1, 1),
            model_key="omega:210.30.42",
            condition_tag=Condition.BOX,
            dedupe_hash="old-hash",
        )
        current = Deal(
            source="fb",
            raw_title="Omega Seamaster 210.30.42 with box",
            ask_vnd=70_000_000,
            url="https://example.invalid/current",
            seen_at=date(2026, 8, 1),
            model_key="omega:210.30.42",
            condition_tag=Condition.BOX,
            dedupe_hash="current-hash",
        )
        insert_deal_if_new(self.conn, old, NOW)
        current_id = insert_deal_if_new(self.conn, current, NOW)

        rows = fetch_unquoted_deals(
            self.conn, since=date(2026, 7, 1), until=date(2026, 8, 1)
        )

        self.assertEqual([row.id for row in rows], [current_id])

    def test_quote_insert_returns_id(self) -> None:
        quote_id = insert_quote(
            self.conn,
            model_key="omega:210.30.42",
            condition_tag=Condition.BOX,
            form=WatchForm.ROUND,
            title="Omega",
            cost_vnd=1_000_000,
            sample_size=0,
            attempt_count=0,
            sell_through_rate=0.0,
            net_min_eur=None,
            net_avg_eur=None,
            net_max_eur=None,
            hammer_p25_eur=None,
            hammer_median_eur=None,
            hammer_p75_eur=None,
            median_days_to_close=None,
            threshold_eur=50.0,
            verdict="insufficient_data",
            assumptions={"audit_version": 0, "legacy_snapshot": "unavailable"},
            comparables=(),
            deal_id=None,
            alert_payload=None,
            now=NOW,
        )
        self.assertGreater(quote_id, 0)
        self.assertEqual(
            fetch_quote_audit(self.conn, quote_id)["assumptions"],
            {"audit_version": 0, "legacy_snapshot": "unavailable"},
        )

    def test_alert_must_be_claimed_before_marking_sent(self) -> None:
        insert_quote(
            self.conn,
            model_key="omega:210.30.42",
            condition_tag=Condition.BOX,
            form=WatchForm.ROUND,
            title="Omega",
            cost_vnd=1_000_000,
            sample_size=0,
            attempt_count=0,
            sell_through_rate=0.0,
            net_min_eur=None,
            net_avg_eur=None,
            net_max_eur=None,
            hammer_p25_eur=None,
            hammer_median_eur=None,
            hammer_p75_eur=None,
            median_days_to_close=None,
            threshold_eur=50.0,
            verdict="green",
            assumptions={"audit_version": 0, "legacy_snapshot": "unavailable"},
            comparables=(),
            alert_payload={"title": "Omega"},
            deal_id=None,
            now=NOW,
        )
        with self.assertRaises(StorageError):
            mark_alert_sent(self.conn, 1, NOW)

    def test_invalid_outbox_payload_is_not_claimed(self) -> None:
        insert_quote(
            self.conn,
            model_key="omega:210.30.42",
            condition_tag=Condition.BOX,
            form=WatchForm.ROUND,
            title="Omega",
            cost_vnd=1_000_000,
            sample_size=0,
            attempt_count=0,
            sell_through_rate=0.0,
            net_min_eur=None,
            net_avg_eur=None,
            net_max_eur=None,
            hammer_p25_eur=None,
            hammer_median_eur=None,
            hammer_p75_eur=None,
            median_days_to_close=None,
            threshold_eur=50.0,
            verdict="green",
            assumptions={"audit_version": 0, "legacy_snapshot": "unavailable"},
            comparables=(),
            alert_payload={"title": "Omega"},
            deal_id=None,
            now=NOW,
        )
        self.conn.execute("UPDATE alert_outbox SET payload='[]'")

        with self.assertRaises(StorageError):
            claim_pending_alerts(self.conn, NOW)

        status = self.conn.execute("SELECT status FROM alert_outbox").fetchone()["status"]
        self.assertEqual(status, "pending")

    def test_check_constraint_blocks_bad_direct_write(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """
                INSERT INTO lots (lot_id, source, title, brand, model_key, condition_tag,
                                  form, hearts, sold, hammer_eur, opened_at, ended_at,
                                  url, source_available, updated_at)
                VALUES ('bad', 's', 't', 'b', 'm', 'unknown-condition', 'round', 1, 1, 10,
                        '2026-01-01', '2026-01-02', 'u', '__YES__', '2026-01-02')
                """
            )

    def test_count_rows_rejects_unknown_table(self) -> None:
        with self.assertRaises(StorageError):
            count_rows(self.conn, "lots; DROP TABLE lots")

    def test_liquidity_fetch_includes_unsold(self) -> None:
        self.seed_lots(
            [make_lot("a"), make_lot("b", sold=False)],
        )
        lots = fetch_lots_for_liquidity(self.conn, date(2020, 1, 1))
        self.assertEqual({lot.lot_id for lot in lots}, {"a", "b"})

    def test_search_products_hyphen_and_word_matching(self) -> None:
        from pathlib import Path
        catalog = load_catalog(Path(__file__).resolve().parents[1] / "config" / "catalog.json")
        ensure_catalog(self.conn, catalog, NOW)

        # Reference with hyphen vs without hyphen
        found_dash = search_products(self.conn, "SPB-143")
        self.assertEqual([p.product_id for p in found_dash], ["seiko:prospex-spb143"])
        found_nodash = search_products(self.conn, "SPB143")
        self.assertEqual([p.product_id for p in found_nodash], ["seiko:prospex-spb143"])

        # Model with hyphen vs without hyphen
        found_bay_dash = search_products(self.conn, "Black-Bay-58")
        self.assertEqual([p.product_id for p in found_bay_dash], ["tudor:black-bay-58-79030"])
        found_bay_space = search_products(self.conn, "Black Bay 58")
        self.assertEqual([p.product_id for p in found_bay_space], ["tudor:black-bay-58-79030"])

        # Brand - Model/Ref query
        found_brand_dash = search_products(self.conn, "Seiko - SPB143")
        self.assertEqual([p.product_id for p in found_brand_dash], ["seiko:prospex-spb143"])

    def test_search_products_fuzzy_and_lots_discovery(self) -> None:
        from pathlib import Path
        catalog = load_catalog(Path(__file__).resolve().parents[1] / "config" / "catalog.json")
        ensure_catalog(self.conn, catalog, NOW)

        # Prefix matching
        prefix_results = search_products(self.conn, "sub")
        self.assertIn("rolex:submariner-124060", [p.product_id for p in prefix_results])

        # Fuzzy typo matching against canonical products
        fuzzy_results = search_products(self.conn, "seikoo")
        self.assertIn("seiko:prospex-spb143", [p.product_id for p in fuzzy_results])

        # Seed lots with King models and a negative check (talking watch)
        self.conn.execute(
            """
            INSERT INTO lots (lot_id, source, title, brand, model, model_key, condition_tag, form, hearts, sold, hammer_eur, opened_at, ended_at, url, subtitle, bids_count, updated_at)
            VALUES
            ('lot-k1', 'catawiki', 'King Seiko Hi-Beat', 'seiko', 'King Seiko', 'seiko:king-seiko', 'naked', 'round', 10, 1, 300, '2026-08-01', '2026-08-10', 'https://ex.com/1', '', 5, '2026-08-10T00:00:00Z'),
            ('lot-k2', 'catawiki', 'Rolex Air-King 14000', 'rolex', 'Air-King', 'rolex:air-king', 'naked', 'round', 10, 1, 3000, '2026-08-01', '2026-08-10', 'https://ex.com/2', '', 5, '2026-08-10T00:00:00Z'),
            ('lot-k3', 'catawiki', 'Seiko Talking Watch', 'seiko', 'Talking Watch', 'seiko:talking-watch', 'naked', 'round', 10, 1, 50, '2026-08-01', '2026-08-10', 'https://ex.com/3', '', 5, '2026-08-10T00:00:00Z')
            """
        )
        self.conn.commit()

        # Query 'king' should discover King Seiko and Air-King, but NOT Talking Watch
        king_results = [p.canonical_name for p in search_products(self.conn, "king")]
        self.assertTrue(any("King Seiko" in name for name in king_results))
        self.assertTrue(any("Air-King" in name for name in king_results))
        self.assertFalse(any("Talking Watch" in name for name in king_results))

        # Query 'airking' should discover Air-King
        airking_results = [p.canonical_name for p in search_products(self.conn, "airking")]
        self.assertTrue(any("Air-King" in name for name in airking_results))

        # Insert lots with diameter and Roman numerals
        self.conn.execute(
            """
            INSERT INTO lots (lot_id, source, title, brand, model, model_key, condition_tag, form, hearts, sold, hammer_eur, opened_at, ended_at, url, subtitle, bids_count, case_diameter_mm, updated_at)
            VALUES
            ('lot-dj36-market', 'catawiki', 'Rolex Datejust 36', 'rolex', 'Datejust 36', 'rolex:datejust-36', 'box', 'round', 10, 1, 4200, '2026-08-01', '2026-08-10', 'https://ex.com/dj36', 'Automatic', 12, 36, '2026-08-10T00:00:00Z'),
            ('lot-t3-market', 'catawiki', 'Tissot Automatics III', 'tissot', 'Automatics III', 'tissot:automatics-iii', 'box', 'round', 5, 1, 250, '2026-08-01', '2026-08-10', 'https://ex.com/t3', 'Automatic', 5, 39, '2026-08-10T00:00:00Z'),
            ('lot-m18-market', 'catawiki', 'IWC Mark XVIII', 'iwc', 'Mark XVIII', 'iwc:mark-xviii', 'box', 'round', 12, 1, 3200, '2026-08-01', '2026-08-10', 'https://ex.com/m18', 'Automatic', 8, 40, '2026-08-10T00:00:00Z')
            """
        )
        self.conn.commit()

        # Diameter 36mm & 36 mm search
        d36_results = [p.canonical_name for p in search_products(self.conn, "rolex 36mm")]
        self.assertTrue(any("Datejust 36" in name for name in d36_results))
        d36_sp_results = [p.canonical_name for p in search_products(self.conn, "rolex 36 mm")]
        self.assertTrue(any("Datejust 36" in name for name in d36_sp_results))

        # Roman <-> Arabic numeral search: Tissot 3 <-> Tissot III
        t3_results = [p.canonical_name for p in search_products(self.conn, "tissot 3")]
        self.assertTrue(any("Automatics III" in name for name in t3_results))
        t3_rom_results = [p.canonical_name for p in search_products(self.conn, "tissot iii")]
        self.assertTrue(any("Automatics III" in name for name in t3_rom_results))

        # Mark 18 <-> Mark XVIII
        m18_results = [p.canonical_name for p in search_products(self.conn, "mark 18")]
        self.assertTrue(any("Mark XVIII" in name for name in m18_results))
        m18_rom_results = [p.canonical_name for p in search_products(self.conn, "mark xviii")]
        self.assertTrue(any("Mark XVIII" in name for name in m18_rom_results))

        # fetch_product should resolve market: product IDs
        market_prod = fetch_product(self.conn, "market:seiko-king-seiko")
        self.assertIsNotNone(market_prod)
        self.assertEqual(market_prod.canonical_name, "King Seiko")
        self.assertEqual(market_prod.brand, "seiko")



if __name__ == "__main__":
    unittest.main()
