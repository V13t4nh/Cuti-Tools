"""Offline tests for the minimal buyer price-distribution helpers."""

from __future__ import annotations

from cuti.charts import hammer_histogram, price_position
from cuti.evaluation import comparison_chart_data
from cuti.models import Condition

from support import TODAY, ProjectTestCase, make_lot

QUERY = "Omega Seamaster Diver 300M 210.30.42"


class ScaleOneChartTests(ProjectTestCase):
    def test_hammer_histogram_counts_equal_width_bins(self):
        histogram = hammer_histogram([1, 2, 3, 4], bins=2)
        self.assertEqual(histogram.counts, (2, 2))
        self.assertEqual(histogram.edges, (1.0, 2.5, 4.0))

    def test_price_position_is_none_for_empty_pool(self):
        self.assertIsNone(price_position(100, []))
        self.assertAlmostEqual(price_position(25, [10, 20, 30, 40]), 0.5)
        self.assertAlmostEqual(price_position(10, [10, 10, 20]), 0.5)

    def test_chart_accessor_hides_thin_comparable_pool(self):
        self.seed_lots(
            [make_lot(f"thin-{index}", title=QUERY, condition=Condition.NAKED) for index in range(2)]
        )
        data = comparison_chart_data(
            self.conn,
            self.rules,
            self.settings,
            query=QUERY,
            cost=1000,
            currency="eur",
            condition=Condition.NAKED,
            today=TODAY,
        )
        self.assertEqual(data.hammer_prices_eur, ())
        self.assertIsNone(data.input_hammer_eur)
        self.assertIsNone(price_position(100, list(data.hammer_prices_eur)))
