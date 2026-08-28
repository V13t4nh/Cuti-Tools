"""Pure Buyer decision evaluation over the existing comparable/pricing core."""

from __future__ import annotations

import sqlite3
import math
from dataclasses import dataclass
from datetime import date

from .comparables import ScoredLot
from .config import Settings
from .errors import PricingError, ScrapeError
from .liquidity import heart_to_hammer_rate
from .models import Condition, Verdict
from .normalize import Rules
from .price_limit import max_buy_cost_vnd
from .pricing import PriceQuote, pricing_value, quote


def cost_to_eur(amount: float | int, currency: str, settings: Settings) -> float:
    """Convert a positive buyer amount to the evaluator's EUR contract."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise PricingError("cost must be a number")
    if not math.isfinite(float(amount)) or amount <= 0:
        raise PricingError("cost must be a finite value > 0")
    if currency == "eur":
        return float(amount)
    if currency == "vnd":
        return float(amount) / pricing_value(settings, "eur_vnd_rate")
    raise PricingError("currency must be one of: vnd, eur")


@dataclass(frozen=True, slots=True)
class DealEvaluation:
    """All values needed by the Buyer screen and its CLI equivalent."""

    query: str
    model_key: str
    condition: Condition
    cost_eur: float
    verdict: Verdict
    reason: str
    sample_size: int
    attempt_count: int
    sell_through_rate: float | None
    heart_to_hammer_rate: float | None
    net_p25_eur: float | None
    net_median_eur: float | None
    net_p75_eur: float | None
    threshold_eur: float
    median_days_to_close: float | None
    max_buy_cost_vnd: int | None

    @classmethod
    def from_quote(
        cls,
        *,
        query: str,
        model_key: str,
        condition: Condition,
        price: PriceQuote,
        minimum_comparables: int,
        sell_through_rate: float | None = None,
        heart_to_hammer_rate: float | None = None,
        max_buy_cost_vnd: int | None = None,
    ) -> "DealEvaluation":
        if price.verdict is Verdict.INSUFFICIENT_DATA:
            reason = (
                f"insufficient comparable sales: {price.sample_size} available, "
                f"minimum is {minimum_comparables}"
            )
        elif price.verdict is Verdict.GREEN:
            reason = "p25 net profit exceeds the required threshold"
        elif price.verdict is Verdict.YELLOW:
            reason = "median net profit exceeds the required threshold"
        else:
            reason = "median net profit does not exceed the required threshold"
        return cls(
            query=query,
            model_key=model_key,
            condition=condition,
            cost_eur=price.cost_eur,
            verdict=price.verdict,
            reason=reason,
            sample_size=price.sample_size,
            attempt_count=price.attempt_count,
            sell_through_rate=sell_through_rate,
            heart_to_hammer_rate=heart_to_hammer_rate,
            net_p25_eur=price.net_p25_eur,
            net_median_eur=price.net_median_eur,
            net_p75_eur=price.net_p75_eur,
            threshold_eur=price.threshold_eur,
            median_days_to_close=price.median_days_to_close,
            max_buy_cost_vnd=max_buy_cost_vnd,
        )


def _cost_vnd(cost: float | int, currency: str, settings: Settings) -> int:
    """Adapt the raw buyer input to pricing.quote's VND contract once."""
    if currency == "vnd":
        if isinstance(cost, bool) or not isinstance(cost, (int, float)):
            raise PricingError("cost must be a number")
        if not math.isfinite(float(cost)) or cost <= 0 or not float(cost).is_integer():
            raise PricingError("vnd cost must be a finite whole number > 0")
        return int(cost)
    if currency == "eur":
        cost_eur = cost_to_eur(cost, currency, settings)
        return int(round(cost_eur * pricing_value(settings, "eur_vnd_rate")))
    raise PricingError("currency must be one of: vnd, eur")


def _evaluate_matches(
    *,
    query: str,
    model_key: str,
    condition: Condition,
    matches: list[ScoredLot],
    cost_vnd: int,
    settings: Settings,
) -> tuple[DealEvaluation, PriceQuote, list[int]]:
    """Apply decision rules and quote once for one already-fetched pool."""
    sold = [item for item in matches if item.lot.sold]
    if len(matches) < settings.min_comparables:
        sell_through_rate = None
        heart_rate = None
    else:
        sell_through_rate = len(sold) / len(matches)
        heart_rate = heart_to_hammer_rate([item.lot for item in matches], settings)
    hammers = [item.lot.hammer_eur for item in sold]
    if any(value is None for value in hammers):
        raise ValueError("a sold comparable is missing its hammer price")
    hammer_values = [int(value) for value in hammers if value is not None]
    days_to_close = [item.lot.days_to_close for item in sold]
    price = quote(
        hammer_values,
        days_to_close,
        cost_vnd,
        settings,
        attempt_count=len(matches),
    )
    result = DealEvaluation.from_quote(
        query=query,
        model_key=model_key,
        condition=condition,
        price=price,
        minimum_comparables=settings.min_comparables,
        sell_through_rate=sell_through_rate,
        heart_to_hammer_rate=heart_rate,
        max_buy_cost_vnd=max_buy_cost_vnd(hammer_values, days_to_close, settings),
    )
    return result, price, hammer_values


def evaluate_deal(
    conn: sqlite3.Connection,
    rules: Rules,
    settings: Settings,
    *,
    query: str,
    cost: float | int,
    currency: str,
    condition: Condition | str,
    today: date | None = None,
) -> DealEvaluation:
    """Evaluate one Buyer input without writing to storage or using the network."""
    from .evaluation_chart import _matching_items

    if not query.strip():
        raise ScrapeError("query must not be empty")
    effective_condition = Condition.parse(condition) if isinstance(condition, str) else condition
    reference_day = today or date.today()
    cost_vnd = _cost_vnd(cost, currency, settings)
    model_key, matches = _matching_items(
        conn, rules, settings, query=query, condition=effective_condition, today=reference_day
    )
    result, _, _ = _evaluate_matches(
        query=query,
        model_key=model_key,
        condition=effective_condition,
        matches=matches,
        cost_vnd=cost_vnd,
        settings=settings,
    )
    return result


def comparison_chart_data(*args, **kwargs):
    """Compatibility re-export for the chart accessor's historical location."""
    from .evaluation_chart import comparison_chart_data as chart_data

    return chart_data(*args, **kwargs)


from .evaluation_chart import ComparisonChartData
