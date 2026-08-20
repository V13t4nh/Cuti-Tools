"""Buyer liquidity-series rendering stays a pure accessor-to-recorder bridge."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
import unittest

from cuti.app import _render_liquidity_series
from cuti.liquidity_timeline import LiquidityWindow


class _Recorder:
    def __init__(self) -> None:
        self.metrics: list[tuple[str, object]] = []
        self.bar_charts: list[object] = []
        self.subheaders: list[str] = []

    def metric(self, label: str, value: object) -> None:
        self.metrics.append((label, value))

    def bar_chart(self, value: object) -> None:
        self.bar_charts.append(value)

    def subheader(self, value: str) -> None:
        self.subheaders.append(value)


def _window(*, sell: float, heart: float | None, days: float | None, size: int) -> LiquidityWindow:
    return LiquidityWindow(
        start=date(2025, 10, 1),
        end=date(2025, 12, 31),
        sell_through_rate=sell,
        heart_to_hammer_rate=heart,
        median_days_to_close=days,
        sample_size=size,
        index=0.5,
    )


class BuyerLiquidityRenderTests(unittest.TestCase):
    def test_renders_raw_accessor_values_without_numeric_formatting(self) -> None:
        series = (
            _window(sell=0.123456789, heart=0.234567891, days=17.75, size=6),
            _window(sell=0.987654321, heart=0.876543219, days=2.125, size=8),
        )
        chart = SimpleNamespace(liquidity_series=series)
        recorder = _Recorder()

        _render_liquidity_series(chart, recorder)

        self.assertEqual(recorder.bar_charts, [(0.123456789, 0.987654321)])
        self.assertEqual(
            dict(recorder.metrics),
            {
                "Sell-through gần nhất": 0.987654321,
                "Heart → hammer gần nhất": 0.876543219,
                "Median days to close gần nhất": 2.125,
                "Sample size gần nhất": 8,
            },
        )

    def test_hides_series_and_missing_latest_metrics(self) -> None:
        recorder = _Recorder()
        _render_liquidity_series(SimpleNamespace(liquidity_series=None), recorder)
        self.assertEqual(recorder.subheaders, [])
        self.assertEqual(recorder.metrics, [])
        self.assertEqual(recorder.bar_charts, [])

        recorder = _Recorder()
        _render_liquidity_series(
            SimpleNamespace(
                liquidity_series=(
                    _window(sell=0.4, heart=None, days=None, size=5),
                )
            ),
            recorder,
        )
        labels = {label for label, _value in recorder.metrics}
        self.assertNotIn("Heart → hammer gần nhất", labels)
        self.assertNotIn("Median days to close gần nhất", labels)
        self.assertEqual(dict(recorder.metrics)["Sell-through gần nhất"], 0.4)
        self.assertEqual(dict(recorder.metrics)["Sample size gần nhất"], 5)


if __name__ == "__main__":
    unittest.main()
