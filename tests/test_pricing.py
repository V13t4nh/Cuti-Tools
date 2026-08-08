"""Pricing: percentiles, net proceeds, thresholds, verdict boundaries."""

from __future__ import annotations

import unittest

from cuti.errors import PricingError
from cuti.models import Verdict
from cuti.pricing import (
    decide,
    net_proceeds,
    percentile,
    profit_threshold,
    quote,
    vnd_to_eur,
)

from support import ProjectTestCase


class PercentileTests(unittest.TestCase):
    def test_known_values(self) -> None:
        values = [1, 2, 3, 4]
        self.assertEqual(percentile(values, 0.0), 1.0)
        self.assertEqual(percentile(values, 0.25), 1.75)
        self.assertEqual(percentile(values, 0.5), 2.5)
        self.assertEqual(percentile(values, 0.75), 3.25)
        self.assertEqual(percentile(values, 1.0), 4.0)

    def test_single_value(self) -> None:
        self.assertEqual(percentile([7], 0.25), 7.0)

    def test_unsorted_input_is_sorted(self) -> None:
        self.assertEqual(percentile([4, 1, 3, 2], 0.5), 2.5)

    def test_empty_raises(self) -> None:
        with self.assertRaises(PricingError):
            percentile([], 0.5)

    def test_out_of_range_q_raises(self) -> None:
        with self.assertRaises(PricingError):
            percentile([1, 2], 1.5)


class NetTests(ProjectTestCase):
    def test_formula_matches_spec(self) -> None:
        settings = self.make_settings(
            CUTI_COMMISSION_RATE="0.125",
            CUTI_VAT_ON_COMMISSION_RATE="0.21",
            CUTI_SHIPPING_EUR="35",
        )
        expected = 1000 - 1000 * 0.125 * 1.21 - 35 - 200
        self.assertAlmostEqual(net_proceeds(1000, 200, settings), expected)

    def test_net_can_be_negative(self) -> None:
        settings = self.make_settings()
        self.assertLess(net_proceeds(100, 500, settings), 0)

    def test_rejects_non_positive_hammer(self) -> None:
        with self.assertRaises(PricingError):
            net_proceeds(0, 10, self.settings)

    def test_rejects_negative_cost(self) -> None:
        with self.assertRaises(PricingError):
            net_proceeds(100, -1, self.settings)

    def test_vnd_conversion(self) -> None:
        settings = self.make_settings(CUTI_EUR_VND_RATE="27000")
        self.assertAlmostEqual(vnd_to_eur(27_000_000, settings), 1000.0)

    def test_vnd_conversion_rejects_zero(self) -> None:
        with self.assertRaises(PricingError):
            vnd_to_eur(0, self.settings)

    def test_threshold_uses_margin_or_floor(self) -> None:
        settings = self.make_settings(CUTI_MIN_MARGIN_RATE="0.15", CUTI_MIN_PROFIT_EUR="50")
        self.assertEqual(profit_threshold(100, settings), 50.0)  # floor wins
        self.assertEqual(profit_threshold(1000, settings), 150.0)  # margin wins


class VerdictTests(unittest.TestCase):
    def test_green_when_pessimistic_case_clears_threshold(self) -> None:
        self.assertIs(decide(120, 200, 100), Verdict.GREEN)

    def test_yellow_when_only_median_clears(self) -> None:
        self.assertIs(decide(90, 200, 100), Verdict.YELLOW)

    def test_red_when_median_does_not_clear(self) -> None:
        self.assertIs(decide(10, 90, 100), Verdict.RED)

    def test_boundaries_are_closed_on_the_pessimistic_side(self) -> None:
        self.assertIs(decide(100, 200, 100), Verdict.YELLOW)  # net_min == threshold
        self.assertIs(decide(10, 100, 100), Verdict.RED)  # net_avg == threshold


class QuoteTests(ProjectTestCase):
    def test_insufficient_data_below_min_comparables(self) -> None:
        settings = self.make_settings(CUTI_MIN_COMPARABLES="5")
        result = quote([1000] * 4, [10] * 4, 1_000_000, settings)
        self.assertIs(result.verdict, Verdict.INSUFFICIENT_DATA)
        self.assertIsNone(result.net_min_eur)
        self.assertEqual(result.sample_size, 4)
        self.assertFalse(result.is_actionable)

    def test_exactly_min_comparables_is_enough(self) -> None:
        settings = self.make_settings(CUTI_MIN_COMPARABLES="5")
        result = quote([1000] * 5, [10] * 5, 1_000_000, settings)
        self.assertIsNot(result.verdict, Verdict.INSUFFICIENT_DATA)
        self.assertEqual(result.sample_size, 5)

    def test_green_case_end_to_end(self) -> None:
        settings = self.make_settings(
            CUTI_MIN_COMPARABLES="5", CUTI_EUR_VND_RATE="27000", CUTI_SHIPPING_EUR="35"
        )
        result = quote([5000] * 6, [12] * 6, 27_000_000, settings)  # cost 1000 EUR
        self.assertIs(result.verdict, Verdict.GREEN)
        self.assertTrue(result.is_actionable)
        self.assertEqual(result.median_days_to_close, 12.0)

    def test_red_case_end_to_end(self) -> None:
        settings = self.make_settings(CUTI_MIN_COMPARABLES="5", CUTI_EUR_VND_RATE="27000")
        result = quote([1200] * 6, [12] * 6, 27_000_000, settings)
        self.assertIs(result.verdict, Verdict.RED)

    def test_outlier_does_not_move_the_median(self) -> None:
        settings = self.make_settings(CUTI_MIN_COMPARABLES="5")
        clean = quote([1000, 1000, 1000, 1000, 1000], [5] * 5, 1_000_000, settings)
        noisy = quote([1000, 1000, 1000, 1000, 99_000], [5] * 5, 1_000_000, settings)
        self.assertAlmostEqual(clean.net_avg_eur, noisy.net_avg_eur)

    def test_mismatched_series_lengths_raise(self) -> None:
        with self.assertRaises(PricingError):
            quote([1000, 2000], [5], 1_000_000, self.settings)

    def test_non_positive_comparable_price_raises(self) -> None:
        with self.assertRaises(PricingError):
            quote([1000, 0], [5, 5], 1_000_000, self.settings)

    def test_percentiles_are_ordered(self) -> None:
        settings = self.make_settings(CUTI_MIN_COMPARABLES="5")
        result = quote([900, 1000, 1100, 1200, 1300], [5] * 5, 1_000_000, settings)
        self.assertLessEqual(result.hammer_p25_eur, result.hammer_median_eur)
        self.assertLessEqual(result.hammer_median_eur, result.hammer_p75_eur)
        self.assertLessEqual(result.net_min_eur, result.net_avg_eur)
        self.assertLessEqual(result.net_avg_eur, result.net_max_eur)


if __name__ == "__main__":
    unittest.main()
