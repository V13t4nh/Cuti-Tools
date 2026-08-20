"""Buyer decision and chart data assembled from one comparable pool."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from .config import Settings
from .comparables import ScoredLot, find_comparables
from .charts import cycle_position, heart_acceleration_rate
from .errors import ScrapeError
from .models import Condition
from .normalize import Rules, classify

if TYPE_CHECKING:
    from .evaluation import DealEvaluation


@dataclass(frozen=True, slots=True)
class ComparisonChartData:
    """Sold hammer prices and the buyer's break-even hammer price."""

    hammer_prices_eur: tuple[int, ...]
    input_hammer_eur: float | None
    cycle_position: float | None = None
    heart_acceleration_rate: float | None = None


@dataclass(frozen=True, slots=True)
class BuyerEvaluation:
    """Decision output and optional chart inputs for one Buyer screen render."""

    decision: DealEvaluation
    chart: ComparisonChartData


def _matching_items(
    conn: sqlite3.Connection,
    rules: Rules,
    settings: Settings,
    *,
    query: str,
    condition: Condition,
    today: date,
) -> tuple[str, list[ScoredLot]]:
    classification = classify(query, rules)
    return classification.model_key, find_comparables(
        conn,
        title=query,
        condition=condition,
        rules=rules,
        settings=settings,
        today=today,
    )


def _inputs(
    query: str,
    condition: Condition | str,
    today: date | None,
) -> tuple[Condition, date]:
    if not query.strip():
        raise ScrapeError("query must not be empty")
    effective_condition = Condition.parse(condition) if isinstance(condition, str) else condition
    return effective_condition, today or date.today()


def _chart_metrics(
    matches: list[ScoredLot], settings: Settings, today: date
) -> tuple[float | None, float | None]:
    if len(matches) < settings.min_comparables:
        return None, None
    lots = [item.lot for item in matches]
    window_days = settings.comparable_window_days
    return (
        cycle_position(lots, today=today, window_days=window_days),
        heart_acceleration_rate(lots, today=today, window_days=window_days),
    )


def evaluate_deal_with_chart(
    conn: sqlite3.Connection,
    rules: Rules,
    settings: Settings,
    *,
    query: str,
    cost: float | int,
    currency: str,
    condition: Condition | str,
    today: date | None = None,
) -> BuyerEvaluation:
    """Evaluate a Buyer input and prepare its chart from one pool and one quote."""
    from .evaluation import _cost_vnd, _evaluate_matches

    effective_condition, reference_day = _inputs(query, condition, today)
    cost_vnd = _cost_vnd(cost, currency, settings)
    model_key, matches = _matching_items(
        conn,
        rules,
        settings,
        query=query,
        condition=effective_condition,
        today=reference_day,
    )
    decision, price, hammers = _evaluate_matches(
        query=query,
        model_key=model_key,
        condition=effective_condition,
        matches=matches,
        cost_vnd=cost_vnd,
        settings=settings,
    )
    cycle, acceleration = _chart_metrics(matches, settings, reference_day)
    chart = ComparisonChartData(
        hammer_prices_eur=tuple(hammers) if len(matches) >= settings.min_comparables else (),
        input_hammer_eur=(
            price.break_even_hammer_eur if len(matches) >= settings.min_comparables else None
        ),
        cycle_position=cycle,
        heart_acceleration_rate=acceleration,
    )
    return BuyerEvaluation(decision=decision, chart=chart)


def comparison_chart_data(
    conn: sqlite3.Connection,
    rules: Rules,
    settings: Settings,
    *,
    query: str,
    cost: float | int,
    currency: str,
    condition: Condition | str,
    today: date | None = None,
) -> ComparisonChartData:
    """Return chart inputs without adding chart state to ``DealEvaluation``."""
    from .evaluation import _cost_vnd, _evaluate_matches

    effective_condition, reference_day = _inputs(query, condition, today)
    cost_vnd = _cost_vnd(cost, currency, settings)
    model_key, matches = _matching_items(
        conn,
        rules,
        settings,
        query=query,
        condition=effective_condition,
        today=reference_day,
    )
    if len(matches) < settings.min_comparables:
        cycle, acceleration = _chart_metrics(matches, settings, reference_day)
        return ComparisonChartData(
            hammer_prices_eur=(),
            input_hammer_eur=None,
            cycle_position=cycle,
            heart_acceleration_rate=acceleration,
        )
    _, price, hammers = _evaluate_matches(
        query=query,
        model_key=model_key,
        condition=effective_condition,
        matches=matches,
        cost_vnd=cost_vnd,
        settings=settings,
    )
    cycle, acceleration = _chart_metrics(matches, settings, reference_day)
    return ComparisonChartData(
        hammer_prices_eur=tuple(hammers),
        input_hammer_eur=price.break_even_hammer_eur,
        cycle_position=cycle,
        heart_acceleration_rate=acceleration,
    )
