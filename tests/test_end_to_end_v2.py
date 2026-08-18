"""Regression coverage for v2 matching, audit, reliability and analytics."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from cuti.charts import heart_acceleration, price_histogram, quarterly_median
from cuti.errors import FetchError, NormalizationError, ScrapeError, StorageError
from cuti.liquidity import compute_liquidity
from cuti.models import Condition, WatchForm
from cuti.normalize import classify, detect_condition, model_key, reference_tokens
from cuti.notifier import build_notifier
from cuti.pipeline import ingest_lots, quote_watch, watch_deals
from cuti.storage import connect, count_rows, fetch_quote_audit, outbox_counts, upsert_lots

from support import NOW, TODAY, ProjectTestCase, make_lot


class ConditionAndReferenceTests(ProjectTestCase):
    def test_partial_negative_preserves_known_accessory(self) -> None:
        self.assertIs(
            detect_condition("Omega 210.30.42 with papers no box", self.rules),
            Condition.PAPERS,
        )
        self.assertIs(
            detect_condition("Omega 210.30.42 with box no papers", self.rules),
            Condition.BOX,
        )

    def test_both_negatives_mean_naked_and_fullset_conflict_raises(self) -> None:
        self.assertIs(
            detect_condition("Omega 210.30.42 không hộp không giấy", self.rules),
            Condition.NAKED,
        )
        with self.assertRaises(NormalizationError):
            detect_condition("Omega 210.30.42 full set no box", self.rules)

    def test_vietnamese_positive_conditions_and_accents(self) -> None:
        self.assertIs(
            detect_condition("Omega 210.30.42 đủ hộp sổ", self.rules),
            Condition.FULLSET,
        )
        self.assertIs(
            detect_condition("Omega 210.30.42 có hộp nhưng mất giấy", self.rules),
            Condition.BOX,
        )
        self.assertIs(
            detect_condition("Omega 210.30.42 co\u0301 gia\u0302\u0301y", self.rules),
            Condition.PAPERS,
        )

    def test_reference_parser_accepts_real_formats_not_marketing_dimensions(self) -> None:
        self.assertEqual(reference_tokens("Seiko Prospex SPB143 300M", self.rules), ("spb143",))
        self.assertEqual(reference_tokens("Longines Spirit L3.812", self.rules), ("l3.812",))
        self.assertEqual(
            reference_tokens("Omega Seamaster 300M 210.30.42", self.rules),
            ("210.30.42",),
        )

    def test_uncued_year_is_not_a_reference_or_model_token(self) -> None:
        self.assertEqual(
            reference_tokens(
                "Omega Seamaster 210.30.42 2020 full set", self.rules
            ),
            ("210.30.42",),
        )
        classification = classify("Tissot PRX 2020 full set", self.rules)
        self.assertEqual(classification.references, ())
        self.assertEqual(classification.model_key, "tissot:prx")
        self.assertEqual(
            reference_tokens("Rolex Datejust ref 2020 full set", self.rules),
            ("2020",),
        )

    def test_price_critical_identity_tokens_separate_text_only_variants(self) -> None:
        self.assertEqual(
            model_key("Tissot PRX quartz watch only", self.rules),
            "tissot:prx quartz",
        )
        self.assertEqual(
            model_key("Tissot PRX automatic watch only", self.rules),
            "tissot:prx automatic",
        )

    def test_multiple_references_are_non_actionable(self) -> None:
        with self.assertRaises(NormalizationError):
            quote_watch(
                self.conn,
                self.rules,
                self.settings,
                title="Rolex Datejust 126234 126233 full set",
                cost_vnd=100_000_000,
                condition=Condition.FULLSET,
                today=TODAY,
                now=NOW,
            )
        self.assertEqual(count_rows(self.conn, "quotes"), 0)


class ComparableAuditTests(ProjectTestCase):
    def setUp(self) -> None:
        super().setUp()
        correct = [
            make_lot(f"right-{i}", hammer_eur=4000 + i * 100)
            for i in range(5)
        ]
        unsold = [make_lot(f"unsold-{i}", sold=False) for i in range(2)]
        wrong = [
            make_lot(
                f"wrong-{i}",
                title="Omega Seamaster Diver 300M 210.30.43 watch only",
                model_key="omega:210.30.43",
                hammer_eur=20_000,
            )
            for i in range(5)
        ]
        self.seed_lots([*correct, *unsold, *wrong])

    def test_exact_reference_and_unsold_attempts_are_enforced(self) -> None:
        report = quote_watch(
            self.conn,
            self.rules,
            self.settings,
            title="Omega Seamaster Diver 300M 210.30.42 watch only",
            cost_vnd=20_000_000,
            condition=Condition.NAKED,
            form=WatchForm.ROUND,
            today=TODAY,
            now=NOW,
        )
        self.assertEqual(report.price.sample_size, 5)
        self.assertEqual(report.price.attempt_count, 7)
        self.assertAlmostEqual(report.price.sell_through_rate, 5 / 7)
        audit = fetch_quote_audit(self.conn, report.quote_id)
        self.assertEqual(len(audit["comparables"]), 7)
        self.assertTrue(all(row["model_key"] == "omega:210.30.42" for row in audit["comparables"]))
        self.assertEqual(audit["assumptions"]["audit_version"], 2)
        self.assertEqual(len(audit["assumptions"]["rules_sha256"]), 64)

    def test_snapshot_does_not_change_when_live_lot_changes(self) -> None:
        report = quote_watch(
            self.conn,
            self.rules,
            self.settings,
            title="Omega Seamaster Diver 300M 210.30.42 watch only",
            cost_vnd=20_000_000,
            condition=Condition.NAKED,
            today=TODAY,
            now=NOW,
        )
        before = fetch_quote_audit(self.conn, report.quote_id)["comparables"]
        upsert_lots(
            self.conn,
            [make_lot("right-0", title="Omega corrected 210.30.42 watch only", hammer_eur=9999)],
            NOW,
        )
        after = fetch_quote_audit(self.conn, report.quote_id)["comparables"]
        self.assertEqual(before, after)

    def test_text_only_model_uses_fts_then_exact_and_fuzzy_gates(self) -> None:
        self.seed_lots(
            [
                make_lot(
                    f"prx-{index}",
                    title="Tissot PRX quartz watch only",
                    brand="tissot",
                    model_key="tissot:prx quartz",
                    hammer_eur=500,
                )
                for index in range(5)
            ]
        )
        report = quote_watch(
            self.conn,
            self.rules,
            self.settings,
            title="Tissot PRX quartz watch only",
            cost_vnd=1_000_000,
            condition=Condition.NAKED,
            today=TODAY,
            now=NOW,
        )
        self.assertEqual(report.price.sample_size, 5)

    def test_text_only_movement_variants_never_cross_match(self) -> None:
        self.seed_lots(
            [
                make_lot(
                    f"automatic-{index}",
                    title="Tissot PRX automatic watch only",
                    brand="tissot",
                    model_key="tissot:prx automatic",
                    hammer_eur=1_000,
                )
                for index in range(5)
            ]
        )
        report = quote_watch(
            self.conn,
            self.rules,
            self.settings,
            title="Tissot PRX quartz watch only",
            cost_vnd=1_000_000,
            condition=Condition.NAKED,
            today=TODAY,
            now=NOW,
        )
        self.assertEqual(report.price.sample_size, 0)

    def test_matching_does_not_silently_truncate_after_500_candidates(self) -> None:
        self.seed_lots(
            [
                make_lot(
                    f"bulk-{index:03d}",
                    title="Tissot PRX quartz watch only",
                    brand="tissot",
                    model_key="tissot:prx quartz",
                    hammer_eur=500 + index,
                )
                for index in range(501)
            ]
        )
        report = quote_watch(
            self.conn,
            self.rules,
            self.settings,
            title="Tissot PRX quartz watch only",
            cost_vnd=1_000_000,
            condition=Condition.NAKED,
            today=TODAY,
            now=NOW,
        )
        self.assertEqual(report.price.sample_size, 501)
        self.assertEqual(report.price.attempt_count, 501)


class BatchReliabilityTests(ProjectTestCase):
    def _valid_deal(self, **overrides):
        return {
            "source": "fb",
            "title": "Rolex Submariner 124060 full set",
            "ask_vnd": 100_000_000,
            "url": "https://example.invalid/deal",
            "seen_at": TODAY.isoformat(),
            "condition": "fullset",
            "form": "round",
            **overrides,
        }

    def _seed_green_market(self) -> None:
        self.seed_lots(
            [
                make_lot(
                    f"sub-{i}",
                    title="Rolex Submariner 124060 full set",
                    brand="rolex",
                    model_key="rolex:124060",
                    condition=Condition.FULLSET,
                    hammer_eur=14_000,
                )
                for i in range(6)
            ]
        )

    def test_malformed_feed_has_zero_writes(self) -> None:
        path = self.write_json(
            "data/batch/deals.json",
            [self._valid_deal(), {key: value for key, value in self._valid_deal().items() if key != "form"}],
        )
        settings = self.make_settings(CUTI_DEALS_SOURCE_URL=str(path))
        with self.assertRaises(ScrapeError):
            watch_deals(self.conn, self.rules, settings, build_notifier(settings), today=TODAY, now=NOW)
        self.assertEqual(count_rows(self.conn, "deals"), 0)

    def test_unknown_brand_has_zero_writes(self) -> None:
        path = self.write_json(
            "data/batch/unknown.json",
            [self._valid_deal(), self._valid_deal(title="Unknownbrand X1 full set", url="https://example.invalid/2")],
        )
        settings = self.make_settings(CUTI_DEALS_SOURCE_URL=str(path))
        with self.assertRaises(NormalizationError):
            watch_deals(self.conn, self.rules, settings, build_notifier(settings), today=TODAY, now=NOW)
        self.assertEqual(count_rows(self.conn, "deals"), 0)

    def test_stale_and_future_deals_are_not_stored(self) -> None:
        path = self.write_json(
            "data/batch/stale.json",
            [
                self._valid_deal(seen_at="2025-01-01"),
                self._valid_deal(seen_at="2026-08-02", url="https://example.invalid/future"),
            ],
        )
        settings = self.make_settings(CUTI_DEALS_SOURCE_URL=str(path))
        report = watch_deals(
            self.conn, self.rules, settings, build_notifier(settings), today=TODAY, now=NOW
        )
        self.assertEqual(report.deals_stale, 2)
        self.assertEqual(count_rows(self.conn, "deals"), 0)

    def test_failed_alert_retries_without_duplicate_quote(self) -> None:
        class FailingNotifier:
            def send(self, payload):
                raise OSError("temporary outage")

        class RecordingNotifier:
            def __init__(self):
                self.payloads = []

            def send(self, payload):
                self.payloads.append(payload)

        self._seed_green_market()
        path = self.write_json("data/batch/one.json", [self._valid_deal()])
        settings = self.make_settings(CUTI_DEALS_SOURCE_URL=str(path))
        first = watch_deals(self.conn, self.rules, settings, FailingNotifier(), today=TODAY, now=NOW)
        self.assertEqual((first.deals_quoted, first.alerts_failed), (1, 1))
        self.assertEqual(outbox_counts(self.conn)["pending"], 1)
        recorder = RecordingNotifier()
        second = watch_deals(self.conn, self.rules, settings, recorder, today=TODAY, now=NOW)
        self.assertEqual(second.deals_new, 0)
        self.assertEqual(second.alerts_sent, 1)
        self.assertEqual(count_rows(self.conn, "quotes"), 1)
        self.assertEqual(len(recorder.payloads), 1)
        self.assertIn("quote_id", recorder.payloads[0])

    def test_pending_alert_is_drained_even_when_next_feed_fetch_fails(self) -> None:
        class FailingNotifier:
            def send(self, payload):
                raise OSError("temporary outage")

        class RecordingNotifier:
            def __init__(self):
                self.payloads = []

            def send(self, payload):
                self.payloads.append(payload)

        self._seed_green_market()
        path = self.write_json("data/batch/pending.json", [self._valid_deal()])
        settings = self.make_settings(CUTI_DEALS_SOURCE_URL=str(path))
        watch_deals(
            self.conn, self.rules, settings, FailingNotifier(), today=TODAY, now=NOW
        )

        recorder = RecordingNotifier()
        broken = self.make_settings(
            CUTI_DEALS_SOURCE_URL=str(self.home / "missing-feed.json")
        )
        with self.assertRaises(FetchError):
            watch_deals(
                self.conn, self.rules, broken, recorder, today=TODAY, now=NOW
            )
        self.assertEqual(len(recorder.payloads), 1)
        self.assertEqual(outbox_counts(self.conn)["sent"], 1)

    def test_unexpected_quote_failure_is_not_swallowed(self) -> None:
        path = self.write_json("data/batch/bug.json", [self._valid_deal()])
        settings = self.make_settings(CUTI_DEALS_SOURCE_URL=str(path))
        with patch("cuti.pipeline.quote_watch", side_effect=RuntimeError("internal bug")):
            with self.assertRaisesRegex(RuntimeError, "internal bug"):
                watch_deals(
                    self.conn,
                    self.rules,
                    settings,
                    build_notifier(settings),
                    today=TODAY,
                    now=NOW,
                )

    def test_alert_moves_to_dead_after_configured_attempts(self) -> None:
        class FailingNotifier:
            def send(self, payload):
                raise OSError("still unavailable")

        self._seed_green_market()
        path = self.write_json("data/batch/dead.json", [self._valid_deal()])
        settings = self.make_settings(
            CUTI_DEALS_SOURCE_URL=str(path), CUTI_ALERT_MAX_ATTEMPTS="2"
        )
        watch_deals(self.conn, self.rules, settings, FailingNotifier(), today=TODAY, now=NOW)
        second = watch_deals(
            self.conn, self.rules, settings, FailingNotifier(), today=TODAY, now=NOW
        )
        self.assertEqual(second.outbox_dead, 1)
        self.assertEqual(outbox_counts(self.conn)["pending"], 0)

    def test_broken_second_crawl_page_keeps_database_empty(self) -> None:
        valid = (
            '<div class="lot-card" data-lot-id="one" data-title="Omega 210.30.42 watch only" '
            'data-condition="naked" data-form="round" data-hearts="1" data-sold="true" '
            'data-hammer-eur="1000" data-opened-at="2026-01-01" data-ended-at="2026-01-02" '
            'data-url="one.html"></div><a class="pagination-next" href="page-2.html"></a>'
        )
        first = self.write_text("data/crawl/page-1.html", valid)
        self.write_text("data/crawl/page-2.html", "<html>broken</html>")
        settings = self.make_settings(CUTI_LOTS_SOURCE_URL=str(first))
        with self.assertRaises(ScrapeError):
            ingest_lots(self.conn, self.rules, settings, NOW)
        self.assertEqual(count_rows(self.conn, "lots"), 0)


class LiquidityAndChartTests(ProjectTestCase):
    def test_two_consecutive_quarter_declines_trigger_stop(self) -> None:
        lots = []
        quarter_specs = (
            (date(2025, 11, 15), 5),
            (date(2026, 2, 15), 3),
            (date(2026, 5, 15), 1),
        )
        counter = 0
        for ended_at, sold_count in quarter_specs:
            for index in range(5):
                counter += 1
                lots.append(
                    make_lot(
                        f"liq-{counter}",
                        ended_at=ended_at,
                        days_open=5,
                        hearts=100,
                        sold=index < sold_count,
                        form=WatchForm.ROUND,
                    )
                )
        self.seed_lots(lots)
        report = compute_liquidity(self.conn, self.settings, TODAY)
        omega = next(item for item in report.brands if item.brand == "omega")
        self.assertTrue(omega.stop_buying)
        self.assertLess(omega.latest_qoq_change, -self.settings.liquidity_decline_rate)

    def test_exactly_twenty_percent_decline_does_not_trigger(self) -> None:
        settings = self.make_settings(
            CUTI_LIQUIDITY_W_SELL_THROUGH="1",
            CUTI_LIQUIDITY_W_SPEED="0",
            CUTI_LIQUIDITY_W_HEARTS="0",
        )
        lots = []
        quarter_specs = (
            (date(2025, 11, 15), 25),
            (date(2026, 2, 15), 20),
            (date(2026, 5, 15), 16),
        )
        counter = 0
        for ended_at, sold_count in quarter_specs:
            for index in range(25):
                counter += 1
                lots.append(
                    make_lot(
                        f"boundary-{counter}",
                        ended_at=ended_at,
                        sold=index < sold_count,
                    )
                )
        self.seed_lots(lots)
        omega = next(
            item for item in compute_liquidity(self.conn, settings, TODAY).brands
            if item.brand == "omega"
        )
        self.assertAlmostEqual(omega.latest_qoq_change, -0.2)
        self.assertFalse(omega.stop_buying)

    def test_figures_render_with_empty_and_nonempty_data(self) -> None:
        empty = []
        self.assertEqual(len(price_histogram(empty, 100).data), 1)
        self.assertEqual(len(quarterly_median(empty).data), 1)
        self.assertEqual(len(heart_acceleration(empty).data), 1)
        lots = [make_lot("chart-1", hearts=50, days_open=5)]
        self.assertTrue(price_histogram(lots, 100).to_json())
        self.assertTrue(quarterly_median(lots).to_json())
        self.assertTrue(heart_acceleration(lots).to_json())


class MigrationTests(unittest.TestCase):
    def test_v1_quote_counts_are_migrated_semantically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.db"
            conn = sqlite3.connect(path)
            conn.executescript(
                """
                CREATE TABLE lots (brand TEXT, ended_at TEXT);
                CREATE TABLE deals (id INTEGER PRIMARY KEY);
                CREATE TABLE quotes (id INTEGER PRIMARY KEY, deal_id INTEGER, sample_size INTEGER);
                INSERT INTO quotes VALUES (1, NULL, 5);
                PRAGMA user_version = 1;
                """
            )
            conn.close()
            migrated = connect(path)
            try:
                row = migrated.execute(
                    "SELECT attempt_count, sell_through_rate, assumptions "
                    "FROM quotes WHERE id=1"
                ).fetchone()
                self.assertEqual((row["attempt_count"], row["sell_through_rate"]), (5, 1.0))
                self.assertEqual(
                    row["assumptions"],
                    '{"audit_version": 1, "legacy_snapshot": "unavailable"}',
                )
                self.assertEqual(migrated.execute("PRAGMA user_version").fetchone()[0], 3)
            finally:
                migrated.close()

    def test_future_schema_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "future.db"
            conn = sqlite3.connect(path)
            conn.execute("PRAGMA user_version = 999")
            conn.close()
            with self.assertRaises(StorageError):
                connect(path)


if __name__ == "__main__":
    unittest.main()
