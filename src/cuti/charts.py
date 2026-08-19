"""Plotly figures for the one-page buyer workflow."""

from __future__ import annotations

import sqlite3
import json
from collections import defaultdict
from datetime import date, timedelta
import math
from typing import Any, Iterable

from .config import Settings
from .models import Condition, Lot
from .pricing import percentile
from .storage import fetch_lots_for_liquidity, fetch_lots_for_model
from .report import Histogram, build_histogram


def hammer_histogram(values: list[int], *, bins: int) -> Histogram:
    """Build a deterministic, stdlib-only histogram for hammer prices."""
    if bins < 1:
        raise ValueError(f"bins must be >= 1, got {bins}")
    if not values:
        return Histogram(edges=(), counts=())
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise TypeError("hammer values must be integers")
    # Keep the report's established equal-width convention in one place.
    result = build_histogram(values, bins=bins)
    return Histogram(edges=result.edges, counts=result.counts)


def price_position(value: float, values: list[int]) -> float | None:
    """Return the linearly interpolated percentile position of ``value``."""
    if not values:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("price value must be numeric")
    if not math.isfinite(float(value)):
        raise ValueError("price value must be finite")
    ordered = sorted(values)
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in ordered):
        raise TypeError("hammer values must be numeric")
    if len(ordered) == 1 or ordered[0] == ordered[-1]:
        return 0.0
    if value < ordered[0]:
        return 0.0
    if value > ordered[-1]:
        return 1.0
    for index in range(len(ordered) - 1):
        low, high = ordered[index], ordered[index + 1]
        if low == high:
            continue
        if low <= value <= high:
            return (index + (value - low) / (high - low)) / (len(ordered) - 1)
    raise ValueError("price position could not be determined")


def _quarter_key(day: date) -> tuple[int, int]:
    return day.year, (day.month - 1) // 3


def _window_lots(lots: Iterable[Lot], today: date, days: int) -> list[Lot]:
    start = today - timedelta(days=days - 1)
    return [lot for lot in lots if start <= lot.ended_at <= today]


def cycle_position(
    lots: Iterable[Lot], *, today: date, window_days: int
) -> float | None:
    """Position of the latest quarterly hammer median in the full window."""
    if window_days < 1:
        raise ValueError("window_days must be >= 1")
    grouped: dict[tuple[int, int], list[float]] = defaultdict(list)
    for lot in _window_lots(lots, today, window_days):
        if lot.sold and lot.hammer_eur is not None:
            grouped[_quarter_key(lot.ended_at)].append(float(lot.hammer_eur))
    if len(grouped) < 3:
        return None
    medians = [percentile(grouped[key], 0.5) for key in sorted(grouped)]
    return price_position(medians[-1], medians)


def _heart_speed(lot: Lot) -> float:
    return lot.hearts / max(lot.days_to_close, 1)


def heart_acceleration_rate(
    lots: Iterable[Lot], *, today: date, window_days: int
) -> float | None:
    """Return the relative change in average hearts/day between two windows."""
    if window_days < 1:
        raise ValueError("window_days must be >= 1")
    rows = list(lots)
    latest = _window_lots(rows, today, window_days)
    previous = _window_lots(
        rows, today - timedelta(days=window_days), window_days
    )
    if not latest or not previous:
        return None
    latest_average = sum(_heart_speed(lot) for lot in latest) / len(latest)
    previous_average = sum(_heart_speed(lot) for lot in previous) / len(previous)
    if previous_average == 0:
        return None
    return latest_average / previous_average - 1.0


class _FallbackFigure:
    """Minimal serializable figure for source-only verification.

    The optional Plotly path remains unchanged when the UI extra is installed;
    this keeps analytics tests importable on the stdlib-only runtime.
    """

    def __init__(self, chart_type: str) -> None:
        self.data = ({"type": chart_type},)

    def to_json(self) -> str:
        return json.dumps({"data": self.data}, sort_keys=True)


def model_lots(
    conn: sqlite3.Connection,
    *,
    model_key: str,
    condition: Condition,
    settings: Settings,
    today: date,
) -> list[Lot]:
    since = today - timedelta(days=settings.comparable_window_days)
    return fetch_lots_for_model(conn, model_key, condition, since, today)


def brand_lots(
    conn: sqlite3.Connection, *, brand: str, settings: Settings, today: date
) -> list[Lot]:
    since = today - timedelta(days=settings.comparable_window_days)
    return [
        lot
        for lot in fetch_lots_for_liquidity(conn, since)
        if lot.brand == brand and lot.ended_at <= today
    ]


def price_histogram(lots: Iterable[Lot], cost_eur: float) -> Any:
    prices = [lot.hammer_eur for lot in lots if lot.sold and lot.hammer_eur is not None]
    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError:
        return _FallbackFigure("histogram")

    figure = go.Figure()
    figure.add_trace(go.Histogram(x=prices, name="Hammer", marker_color="#2563eb"))
    figure.add_vline(
        x=cost_eur,
        line_dash="dash",
        line_color="#dc2626",
        annotation_text="Giá vốn",
    )
    figure.update_layout(
        title="Phân phối hammer price (24 tháng)",
        xaxis_title="EUR",
        yaxis_title="Số lot",
        bargap=0.08,
        showlegend=False,
    )
    return figure


def quarterly_median(lots: Iterable[Lot]) -> Any:
    grouped: dict[str, list[float]] = defaultdict(list)
    for lot in lots:
        if lot.sold and lot.hammer_eur is not None:
            quarter = (lot.ended_at.month - 1) // 3 + 1
            grouped[f"{lot.ended_at.year}-Q{quarter}"].append(float(lot.hammer_eur))
    labels = sorted(grouped)
    medians = [percentile(grouped[label], 0.5) for label in labels]
    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError:
        return _FallbackFigure("scatter")

    figure = go.Figure(
        go.Scatter(x=labels, y=medians, mode="lines+markers", line_color="#7c3aed")
    )
    figure.update_layout(
        title="Median theo quý",
        xaxis_title="Quý",
        yaxis_title="EUR",
        showlegend=False,
    )
    return figure


def heart_acceleration(lots: Iterable[Lot]) -> Any:
    rows = list(lots)
    values = [_heart_speed(lot) for lot in rows]
    average = sum(values) / len(values) if values else 0.0
    colors = ["#16a34a" if value >= average else "#94a3b8" for value in values]
    labels = [lot.lot_id for lot in rows]
    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError:
        return _FallbackFigure("bar")

    figure = go.Figure(go.Bar(x=labels, y=values, marker_color=colors))
    if values:
        figure.add_hline(
            y=average,
            line_dash="dot",
            line_color="#dc2626",
            annotation_text="Trung bình cùng brand",
        )
    figure.update_layout(
        title="Gia tốc tim (hearts/ngày mở phiên)",
        xaxis_title="Lot",
        yaxis_title="Hearts/ngày",
        showlegend=False,
    )
    return figure
