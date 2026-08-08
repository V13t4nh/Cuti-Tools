"""Liquidity index and completed-quarter trend by brand and watch form."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from .config import Settings
from .models import Lot, WatchForm
from .pricing import percentile
from .storage import fetch_lots_for_liquidity


@dataclass(frozen=True, slots=True)
class BrandLiquidity:
    brand: str
    form: WatchForm
    lots: int
    sold: int
    sell_through: float
    median_days_to_close: float | None
    speed: float
    heart_to_hammer: float
    index: float
    latest_qoq_change: float | None
    stop_buying: bool


@dataclass(frozen=True, slots=True)
class LiquidityReport:
    window_start: date
    window_end: date
    brands: tuple[BrandLiquidity, ...]
    excluded_groups: tuple[tuple[str, WatchForm, int], ...]

    @property
    def excluded_brands(self) -> tuple[tuple[str, int], ...]:
        """Backward-compatible aggregate for older CLI callers."""
        totals: dict[str, int] = {}
        for brand, _form, lots in self.excluded_groups:
            totals[brand] = totals.get(brand, 0) + lots
        return tuple(sorted(totals.items()))


def _metrics(lots: list[Lot], settings: Settings) -> tuple[int, float, float | None, float, float, float]:
    sold_lots = [lot for lot in lots if lot.sold]
    sell_through = len(sold_lots) / len(lots)
    if sold_lots:
        median_days = percentile([float(lot.days_to_close) for lot in sold_lots], 0.50)
        speed = min(1.0, settings.liquidity_ref_days / max(median_days, 1.0))
    else:
        median_days = None
        speed = 0.0
    hot_lots = [lot for lot in lots if lot.hearts >= settings.liquidity_hot_hearts]
    heart_to_hammer = (
        sum(1 for lot in hot_lots if lot.sold) / len(hot_lots) if hot_lots else 0.0
    )
    index = (
        settings.liquidity_w_sell_through * sell_through
        + settings.liquidity_w_speed * speed
        + settings.liquidity_w_hearts * heart_to_hammer
    )
    return len(sold_lots), sell_through, median_days, speed, heart_to_hammer, index


def _quarter_start(day: date) -> date:
    return date(day.year, ((day.month - 1) // 3) * 3 + 1, 1)


def _previous_completed_quarters(today: date, count: int = 3) -> tuple[tuple[date, date], ...]:
    end = _quarter_start(today) - timedelta(days=1)
    periods: list[tuple[date, date]] = []
    for _ in range(count):
        start = _quarter_start(end)
        periods.append((start, end))
        end = start - timedelta(days=1)
    periods.reverse()
    return tuple(periods)


def _quarterly_trend(lots: list[Lot], settings: Settings, today: date) -> tuple[float | None, bool]:
    indexes: list[float] = []
    for start, end in _previous_completed_quarters(today):
        quarter_lots = [lot for lot in lots if start <= lot.ended_at <= end]
        if len(quarter_lots) < settings.liquidity_min_lots:
            return None, False
        indexes.append(_metrics(quarter_lots, settings)[-1])
    if indexes[0] <= 0 or indexes[1] <= 0:
        return None, False
    changes = (indexes[1] / indexes[0] - 1.0, indexes[2] / indexes[1] - 1.0)
    stop_buying = all(change < -settings.liquidity_decline_rate for change in changes)
    return changes[-1], stop_buying


def _score_group(
    brand: str,
    form: WatchForm,
    lots: list[Lot],
    settings: Settings,
    today: date,
) -> BrandLiquidity:
    sold, sell_through, median_days, speed, heart_to_hammer, index = _metrics(lots, settings)
    latest_change, stop_buying = _quarterly_trend(lots, settings, today)
    return BrandLiquidity(
        brand=brand,
        form=form,
        lots=len(lots),
        sold=sold,
        sell_through=sell_through,
        median_days_to_close=median_days,
        speed=speed,
        heart_to_hammer=heart_to_hammer,
        index=index,
        latest_qoq_change=latest_change,
        stop_buying=stop_buying,
    )


def compute_liquidity(
    conn: sqlite3.Connection, settings: Settings, today: date
) -> LiquidityReport:
    """Rank brand/form groups and detect two completed quarters of decline."""
    start = today - timedelta(days=settings.comparable_window_days)
    grouped: dict[tuple[str, WatchForm], list[Lot]] = {}
    for lot in fetch_lots_for_liquidity(conn, start):
        if lot.ended_at <= today:
            grouped.setdefault((lot.brand, lot.form), []).append(lot)

    scored: list[BrandLiquidity] = []
    excluded: list[tuple[str, WatchForm, int]] = []
    for (brand, form), lots in grouped.items():
        if len(lots) < settings.liquidity_min_lots:
            excluded.append((brand, form, len(lots)))
            continue
        scored.append(_score_group(brand, form, lots, settings, today))

    scored.sort(key=lambda item: (-item.index, item.brand, item.form.value))
    excluded.sort(key=lambda item: (item[0], item[1].value))
    return LiquidityReport(
        window_start=start,
        window_end=today,
        brands=tuple(scored),
        excluded_groups=tuple(excluded),
    )
