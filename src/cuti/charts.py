"""Plotly figures for the one-page buyer workflow."""

from __future__ import annotations

import sqlite3
import json
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable

from .config import Settings
from .models import Condition, Lot
from .pricing import percentile
from .storage import fetch_lots_for_liquidity, fetch_lots_for_model


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
    values = [lot.hearts / max(lot.days_to_close, 1) for lot in rows]
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
