"""Scale 3 regression coverage for liquidity timeline and status output."""

from datetime import date
import io
import json
from contextlib import redirect_stdout

from cuti.cli import main
from cuti.liquidity import liquidity_series, liquidity_status, liquidity_windows
from cuti.models import WatchForm

from support import ProjectTestCase, make_lot


class LiquidityTimelineTests(ProjectTestCase):
    def _quarter_lots(self, prefix: str, ended_at: date, sold: int) -> list:
        return [
            make_lot(
                f"{prefix}-{index}",
                ended_at=ended_at,
                sold=index < sold,
                hearts=100,
                form=WatchForm.ROUND,
            )
            for index in range(5)
        ]

    def test_timeline_uses_configured_window_and_reuses_metrics(self) -> None:
        settings = self.make_settings(CUTI_COMPARABLE_WINDOW_DAYS="365")
        lots = []
        for prefix, ended_at, sold in (
            ("q3", date(2025, 9, 15), 5),
            ("q4", date(2025, 12, 15), 4),
            ("q1", date(2026, 3, 15), 3),
            ("q2", date(2026, 6, 15), 2),
        ):
            lots.extend(self._quarter_lots(prefix, ended_at, sold))
        windows = liquidity_windows(lots, settings, date(2026, 8, 1))
        self.assertEqual(len(windows), 4)
        self.assertEqual([window.sample_size for window in windows if window], [5, 5, 5, 5])
        self.assertEqual(windows[-1].sell_through_rate, 0.4)
        self.assertEqual(windows[-1].heart_to_hammer_rate, 0.4)
        self.assertEqual(windows[-1].median_days_to_close, 10.0)

    def test_series_drops_thin_quarters_and_keeps_periods(self) -> None:
        settings = self.make_settings(CUTI_LIQUIDITY_MIN_LOTS="1")
        periods = (
            date(2024, 9, 15), date(2024, 12, 15), date(2025, 3, 15),
            date(2025, 6, 15), date(2025, 9, 15), date(2025, 12, 15),
            date(2026, 3, 15), date(2026, 6, 15),
        )
        lots = [make_lot(f"quarter-{index}", ended_at=ended_at) for index, ended_at in enumerate(periods)]
        series = liquidity_series(lots, settings, date(2026, 8, 1))
        self.assertIsNotNone(series)
        self.assertEqual(len(series), 8)

        sparse = [lots[0], lots[-1]]
        sparse_series = liquidity_series(sparse, settings, date(2026, 8, 1))
        self.assertEqual(len(sparse_series or ()), 2)
        self.assertEqual(sparse_series[0].start, date(2024, 7, 1))
        self.assertEqual(sparse_series[-1].start, date(2026, 4, 1))

    def test_series_is_none_when_only_one_quarter_has_enough_lots(self) -> None:
        settings = self.make_settings(CUTI_LIQUIDITY_MIN_LOTS="1")
        lots = [make_lot("only-quarter", ended_at=date(2026, 6, 15))]
        self.assertIsNone(liquidity_series(lots, settings, date(2026, 8, 1)))

    def test_series_is_none_when_no_quarter_has_enough_lots(self) -> None:
        settings = self.make_settings(CUTI_LIQUIDITY_MIN_LOTS="2")
        lots = [make_lot("one-lot", ended_at=date(2026, 6, 15))]
        self.assertIsNone(liquidity_series(lots, settings, date(2026, 8, 1)))

    def test_missing_window_is_none_and_status_requires_two_windows(self) -> None:
        settings = self.make_settings(CUTI_COMPARABLE_WINDOW_DAYS="365")
        lots = self._quarter_lots("latest", date(2026, 6, 15), 5)
        windows = liquidity_windows(lots, settings, date(2026, 8, 1))
        self.assertIsNone(windows[0])
        self.assertIsNone(liquidity_status(windows, settings))

    def test_first_partial_quarter_respects_configured_cutoff(self) -> None:
        settings = self.make_settings(CUTI_COMPARABLE_WINDOW_DAYS="365")
        lots = [make_lot("before-cutoff", ended_at=date(2025, 7, 31))]
        lots.extend(self._quarter_lots("q3", date(2025, 9, 15), 4)[:4])
        windows = liquidity_windows(lots, settings, date(2026, 8, 1))
        self.assertIsNone(windows[0])

    def test_status_uses_decline_threshold_for_all_three_states(self) -> None:
        settings = self.make_settings(CUTI_COMPARABLE_WINDOW_DAYS="365")
        today = date(2026, 8, 1)

        def status(previous_sold: int, latest_sold: int) -> str | None:
            lots = self._quarter_lots("previous", date(2026, 3, 15), previous_sold)
            lots.extend(self._quarter_lots("latest", date(2026, 6, 15), latest_sold))
            return liquidity_status(liquidity_windows(lots, settings, today), settings)

        self.assertEqual(status(5, 0), "declining")
        self.assertEqual(status(5, 5), "stable")
        self.assertEqual(status(1, 5), "improving")

    def test_status_is_none_when_latest_or_prior_window_is_missing(self) -> None:
        settings = self.make_settings(CUTI_COMPARABLE_WINDOW_DAYS="365")
        today = date(2026, 8, 1)
        prior = self._quarter_lots("prior", date(2026, 3, 15), 5)
        latest_missing = liquidity_windows(prior, settings, today)
        self.assertIsNone(liquidity_status(latest_missing, settings))


class LiquidityCliScale3Tests(ProjectTestCase):
    def test_existing_liquidity_index_rows_are_unchanged(self) -> None:
        (self.home / ".env").write_text(
            f"CUTI_LOTS_SOURCE_URL={self.home}/data/sample/catawiki/page-1.html\n"
            f"CUTI_DEALS_SOURCE_URL={self.home}/data/sample/deals/deals.json\n",
            encoding="utf-8",
        )
        self.conn.close()
        args = ["--home", str(self.home), "--today", "2026-08-01", "--json"]
        self.assertEqual(main([*args, "ingest"]), 0)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([*args, "liquidity"]), 0)
        payload = json.loads(output.getvalue())
        actual = {row["brand"]: round(row["index"], 3) for row in payload["brands"]}
        self.assertEqual(
            {brand: actual[brand] for brand in ("omega", "oris", "rolex", "citizen", "seiko")},
            {"omega": 0.935, "oris": 0.875, "rolex": 0.858, "citizen": 0.847, "seiko": 0.834},
        )
        text_output = io.StringIO()
        with redirect_stdout(text_output):
            self.assertEqual(main([*args[0:4], "liquidity"]), 0)
        self.assertIn("status", text_output.getvalue().splitlines()[0])
        self.assertTrue(all("status" in row for row in payload["brands"]))
