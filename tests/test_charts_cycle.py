from __future__ import annotations

import unittest
from datetime import date

from cuti.charts import cycle_position, heart_acceleration_rate
from support import make_lot


TODAY = date(2026, 8, 1)


class CyclePositionTests(unittest.TestCase):
    def test_rising_quarters_are_at_cycle_peak(self) -> None:
        lots = [
            make_lot("q1", ended_at=date(2025, 10, 1), hammer_eur=100),
            make_lot("q2", ended_at=date(2026, 1, 1), hammer_eur=200),
            make_lot("q3", ended_at=date(2026, 4, 1), hammer_eur=300),
        ]
        self.assertEqual(cycle_position(lots, today=TODAY, window_days=730), 1.0)

    def test_falling_quarters_are_at_cycle_floor(self) -> None:
        lots = [
            make_lot("q1", ended_at=date(2025, 10, 1), hammer_eur=300),
            make_lot("q2", ended_at=date(2026, 1, 1), hammer_eur=200),
            make_lot("q3", ended_at=date(2026, 4, 1), hammer_eur=100),
        ]
        self.assertEqual(cycle_position(lots, today=TODAY, window_days=730), 0.0)

    def test_cycle_position_needs_three_quarters(self) -> None:
        lots = [
            make_lot("q1", ended_at=date(2026, 1, 1), hammer_eur=100),
            make_lot("q2", ended_at=date(2026, 4, 1), hammer_eur=200),
        ]
        self.assertIsNone(cycle_position(lots, today=TODAY, window_days=730))


class HeartAccelerationTests(unittest.TestCase):
    def test_positive_rate_means_hearts_are_heating_up(self) -> None:
        lots = [
            make_lot("old", ended_at=date(2026, 6, 15), hearts=10),
            make_lot("new", ended_at=date(2026, 7, 15), hearts=20),
        ]
        self.assertGreater(
            heart_acceleration_rate(lots, today=TODAY, window_days=30), 0.0
        )

    def test_negative_rate_means_hearts_are_cooling(self) -> None:
        lots = [
            make_lot("old", ended_at=date(2026, 6, 15), hearts=20),
            make_lot("new", ended_at=date(2026, 7, 15), hearts=10),
        ]
        self.assertLess(
            heart_acceleration_rate(lots, today=TODAY, window_days=30), 0.0
        )

    def test_heart_acceleration_needs_both_windows(self) -> None:
        lots = [make_lot("new", ended_at=date(2026, 7, 15), hearts=20)]
        self.assertIsNone(
            heart_acceleration_rate(lots, today=TODAY, window_days=30)
        )


if __name__ == "__main__":
    unittest.main()
