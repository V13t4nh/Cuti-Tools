"""Pure Buyer decision evaluation over the existing comparable/pricing core."""

from __future__ import annotations

import sqlite3
import math
from dataclasses import dataclass
from datetime import date

from .comparables import find_comparables
from .config import Settings
from .errors import PricingError, ScrapeError
from .models import Condition, Verdict
from .normalize import Rules, classify
from .pricing import PriceQuote, quote


def cost_to_eur(amount: float | int, currency: str, settings: Settings) -> float:
    """Convert a positive buyer amount to the evaluator's EUR contract."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise PricingError("cost must be a number")
    if not math.isfinite(float(amount)) or amount <= 0:
        raise PricingError("cost must be a finite value > 0")
    if currency == "eur":
        return float(amount)
    if currency == "vnd":
        return float(amount) / settings.eur_vnd_rate
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
    liquidity_index: float
    net_p25_eur: float | None
    net_median_eur: float | None
    net_p75_eur: float | None
    threshold_eur: float
    median_days_to_close: float | None

    @property
    def liquidity_sell_through(self) -> float:
        """Condition/model sell-through, used as the liquidity indicator."""
        return self.liquidity_index

    @property
    def net_profit_p25_eur(self) -> float | None:
        return self.net_p25_eur

    @property
    def net_profit_median_eur(self) -> float | None:
        return self.net_median_eur

    @property
    def net_profit_p75_eur(self) -> float | None:
        return self.net_p75_eur

    @classmethod
    def from_quote(
        cls,
        *,
        query: str,
        model_key: str,
        condition: Condition,
        price: PriceQuote,
        minimum_comparables: int,
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
            liquidity_index=price.sell_through_rate,
            net_p25_eur=price.net_p25_eur,
            net_median_eur=price.net_median_eur,
            net_p75_eur=price.net_p75_eur,
            threshold_eur=price.threshold_eur,
            median_days_to_close=price.median_days_to_close,
        )


def evaluate_deal(
    conn: sqlite3.Connection,
    rules: Rules,
    settings: Settings,
    *,
    query: str,
    cost_eur: float,
    condition: Condition | str,
    today: date | None = None,
) -> DealEvaluation:
    """Evaluate one Buyer input without writing to storage or using the network."""
    if not query.strip():
        raise ScrapeError("query must not be empty")
    effective_condition = Condition.parse(condition) if isinstance(condition, str) else condition
    if isinstance(cost_eur, bool) or not isinstance(cost_eur, (int, float)):
        raise PricingError("cost_eur must be a number")
    if not math.isfinite(float(cost_eur)) or cost_eur <= 0:
        raise PricingError("cost_eur must be a finite value > 0")
    reference_day = today or date.today()
    # pricing.quote's public contract is VND.  Round once at this boundary so
    # VND and EUR adapters converge to the same canonical integer input.
    cost_vnd = int(round(cost_eur * settings.eur_vnd_rate))
    classification = classify(query, rules)
    matches = find_comparables(
        conn,
        title=query,
        condition=effective_condition,
        rules=rules,
        settings=settings,
        today=reference_day,
    )
    sold = [item for item in matches if item.lot.sold]
    hammers = [item.lot.hammer_eur for item in sold]
    if any(value is None for value in hammers):
        raise ValueError("a sold comparable is missing its hammer price")
    price = quote(
        [int(value) for value in hammers if value is not None],
        [item.lot.days_to_close for item in sold],
        cost_vnd,
        settings,
        attempt_count=len(matches),
    )
    return DealEvaluation.from_quote(
        query=query,
        model_key=classification.model_key,
        condition=effective_condition,
        price=price,
        minimum_comparables=settings.min_comparables,
    )
