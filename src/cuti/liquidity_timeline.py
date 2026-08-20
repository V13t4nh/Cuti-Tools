"""Pure calendar-window helpers for liquidity trend accessors.

The module deliberately knows nothing about storage.  Callers provide the
already-fetched lots and the existing metric function, keeping the liquidity
formula in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Sequence


@dataclass(frozen=True, slots=True)
class LiquidityWindow:
    """Metrics for one completed calendar quarter."""

    start: date
    end: date
    sell_through_rate: float
    heart_to_hammer_rate: float | None
    median_days_to_close: float | None
    sample_size: int
    # The index is retained for the trend decision; it is not a second formula.
    index: float

    @property
    def period(self) -> tuple[date, date]:
        return self.start, self.end


def quarter_start(day: date) -> date:
    return date(day.year, ((day.month - 1) // 3) * 3 + 1, 1)


def completed_quarters(today: date, window_days: int) -> tuple[tuple[date, date], ...]:
    """Return completed quarters covered by the existing comparable window."""
    cutoff = today - timedelta(days=window_days)
    end = quarter_start(today) - timedelta(days=1)
    periods: list[tuple[date, date]] = []
    while end >= cutoff:
        start = quarter_start(end)
        periods.append((start, end))
        end = start - timedelta(days=1)
    periods.reverse()
    return tuple(periods)


MetricFn = Callable[
    [list[object], object], tuple[int, float, float | None, float, float | None, float]
]


def build_windows(
    lots: Sequence[object],
    settings: object,
    today: date,
    metric_fn: MetricFn,
) -> tuple[LiquidityWindow | None, ...]:
    """Build quarter metrics, preserving ``None`` for thin windows."""
    windows: list[LiquidityWindow | None] = []
    cutoff = today - timedelta(days=settings.comparable_window_days)
    for start, end in completed_quarters(today, settings.comparable_window_days):
        quarter_lots = [
            lot for lot in lots if cutoff <= lot.ended_at <= end and start <= lot.ended_at
        ]
        if len(quarter_lots) < settings.liquidity_min_lots:
            windows.append(None)
            continue
        _sold, sell_through, median_days, _speed, heart_rate, index = metric_fn(
            quarter_lots, settings
        )
        windows.append(
            LiquidityWindow(
                start=start,
                end=end,
                sell_through_rate=sell_through,
                heart_to_hammer_rate=heart_rate,
                median_days_to_close=median_days,
                sample_size=len(quarter_lots),
                index=index,
            )
        )
    return tuple(windows)


def trend_status(
    windows: Sequence[LiquidityWindow | None], decline_rate: float
) -> str | None:
    """Classify the newest complete quarter against its predecessor."""
    if len(windows) < 2 or windows[-1] is None or windows[-2] is None:
        return None
    previous, latest = windows[-2], windows[-1]
    if previous.index <= 0:
        return None
    change = latest.index / previous.index - 1.0
    if change < -decline_rate:
        return "declining"
    if change > decline_rate:
        return "improving"
    return "stable"
