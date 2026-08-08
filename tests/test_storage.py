"""Storage: schema invariants, idempotent upserts, dedupe, FTS sync."""

from __future__ import annotations

import sqlite3
import unittest
from datetime import date

from cuti.errors import ScrapeError, StorageError
from cuti.models import Condition, Deal, Lot
from cuti.storage import (
    claim_pending_alerts,
    count_rows,
    fetch_quote_audit,
    fetch_lots_for_liquidity,
    fetch_sold_lots_since,
    fetch_unquoted_deals,
    insert_deal_if_new,
    insert_quote,
    mark_alert_sent,
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
            title="Omega",
            cost_vnd=1_000_000,
            sample_size=0,
            net_min_eur=None,
            net_avg_eur=None,
            net_max_eur=None,
            threshold_eur=50.0,
            verdict="insufficient_data",
            deal_id=None,
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
            title="Omega",
            cost_vnd=1_000_000,
            sample_size=0,
            net_min_eur=None,
            net_avg_eur=None,
            net_max_eur=None,
            threshold_eur=50.0,
            verdict="green",
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
            title="Omega",
            cost_vnd=1_000_000,
            sample_size=0,
            net_min_eur=None,
            net_avg_eur=None,
            net_max_eur=None,
            threshold_eur=50.0,
            verdict="green",
            alert_payload={"title": "Omega"},
            deal_id=None,
            now=NOW,
        )
        self.conn.execute("UPDATE alert_outbox SET payload_json='[]'")

        with self.assertRaises(StorageError):
            claim_pending_alerts(self.conn, NOW)

        status = self.conn.execute("SELECT status FROM alert_outbox").fetchone()["status"]
        self.assertEqual(status, "pending")

    def test_check_constraint_blocks_bad_direct_write(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """
                INSERT INTO lots (lot_id, source, title, brand, model_key, condition_tag,
                                  hearts, sold, hammer_eur, opened_at, ended_at,
                                  days_to_close, url, ingested_at)
                VALUES ('bad', 's', 't', 'b', 'm', 'unknown-condition', 1, 1, 10,
                        '2026-01-01', '2026-01-02', 1, 'u', '2026-01-02')
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


if __name__ == "__main__":
    unittest.main()
