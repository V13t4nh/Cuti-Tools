"""Pricing core: percentiles, net proceeds and the traffic-light verdict.

This is the single point every caller (UI, CLI, deal bot) goes through, so the
formula exists exactly once.

    fee   = hammer * commission_rate
    net   = hammer - fee * (1 + vat_on_commission) - shipping - cost

Median/p25/p75 are used instead of mean/stddev: robust to outliers, no
normality assumption.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .config import Settings
from .config_pricing import FormulaError, PricingProfile
from .errors import PricingError
from .models import Verdict


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile (same convention as numpy's default)."""
    if not values:
        raise PricingError("percentile requires at least one value")
    if not 0.0 <= q <= 1.0:
        raise PricingError(f"percentile q must be in [0, 1], got {q}")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = q * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return float(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


def _profile(settings: Settings) -> PricingProfile:
    profile = settings.pricing_profile
    if isinstance(profile, PricingProfile):
        return profile
    from .config_pricing_store import load_pricing_profile
    return load_pricing_profile(settings)


def pricing_value(settings: Settings, name: str) -> float:
    return _profile(settings).values[name]


def vnd_to_eur(amount_vnd: int, settings: Settings) -> float:
    if amount_vnd <= 0:
        raise PricingError(f"amount_vnd must be > 0, got {amount_vnd}")
    return amount_vnd / pricing_value(settings, "eur_vnd_rate")


def net_proceeds(hammer_eur: float, cost_eur: float, settings: Settings) -> float:
    """Profit left after marketplace fee, VAT on the fee, shipping and cost."""
    if hammer_eur <= 0:
        raise PricingError(f"hammer_eur must be > 0, got {hammer_eur}")
    if cost_eur < 0:
        raise PricingError(f"cost_eur must be >= 0, got {cost_eur}")
    return _profile(settings).evaluate("net_proceeds", hammer_eur=hammer_eur, cost_eur=cost_eur)


def profit_threshold(cost_eur: float, settings: Settings) -> float:
    """Minimum acceptable profit: a margin on cost, with an absolute floor."""
    if cost_eur < 0:
        raise PricingError(f"cost_eur must be >= 0, got {cost_eur}")
    return _profile(settings).evaluate("profit_threshold", hammer_eur=1.0, cost_eur=cost_eur)


@dataclass(frozen=True, slots=True)
class PriceQuote:
    """Result of pricing one buying opportunity."""

    verdict: Verdict
    sample_size: int
    attempt_count: int
    sell_through_rate: float
    cost_eur: float
    threshold_eur: float
    net_min_eur: float | None
    net_avg_eur: float | None
    net_max_eur: float | None
    hammer_p25_eur: float | None
    hammer_median_eur: float | None
    hammer_p75_eur: float | None
    median_days_to_close: float | None
    break_even_hammer_eur: float

    @property
    def is_actionable(self) -> bool:
        return self.verdict is Verdict.GREEN

    @property
    def net_p25_eur(self) -> float | None:
        return self.net_min_eur

    @property
    def net_median_eur(self) -> float | None:
        return self.net_avg_eur

    @property
    def net_p75_eur(self) -> float | None:
        return self.net_max_eur


def decide(net_min: float, net_avg: float, threshold: float) -> Verdict:
    """Traffic light. Boundaries are closed on the pessimistic side."""
    if net_min > threshold:
        return Verdict.GREEN
    if net_avg > threshold:
        return Verdict.YELLOW
    return Verdict.RED


def break_even_hammer(cost_eur: float, threshold_eur: float, settings: Settings) -> float:
    """Hammer needed to recover cost, fees, shipping and the profit threshold."""
    if cost_eur < 0 or threshold_eur < 0:
        raise PricingError("cost and threshold must be non-negative")
    try:
        return _profile(settings).inverse_break_even(cost_eur, threshold_eur)
    except FormulaError as exc:
        raise PricingError(str(exc)) from exc


def quote(
    hammer_prices: Sequence[int],
    days_to_close: Sequence[int],
    cost_vnd: int,
    settings: Settings,
    *,
    attempt_count: int | None = None,
) -> PriceQuote:
    """Price one opportunity against its comparables."""
    if len(hammer_prices) != len(days_to_close):
        raise PricingError(
            "hammer_prices and days_to_close must have the same length "
            f"({len(hammer_prices)} != {len(days_to_close)})"
        )
    if any(price <= 0 for price in hammer_prices):
        raise PricingError("every comparable hammer price must be > 0")
    if any(day < 0 for day in days_to_close):
        raise PricingError("every days_to_close value must be >= 0")

    attempts = len(hammer_prices) if attempt_count is None else attempt_count
    if attempts < len(hammer_prices):
        raise PricingError("attempt_count must be >= the number of sold comparables")
    sell_through = len(hammer_prices) / attempts if attempts else 0.0

    cost_eur = vnd_to_eur(cost_vnd, settings)
    threshold = profit_threshold(cost_eur, settings)
    required_hammer = break_even_hammer(cost_eur, threshold, settings)

    if len(hammer_prices) < settings.min_comparables:
        return PriceQuote(
            verdict=Verdict.INSUFFICIENT_DATA,
            sample_size=len(hammer_prices),
            attempt_count=attempts,
            sell_through_rate=sell_through,
            cost_eur=cost_eur,
            threshold_eur=threshold,
            net_min_eur=None,
            net_avg_eur=None,
            net_max_eur=None,
            hammer_p25_eur=None,
            hammer_median_eur=None,
            hammer_p75_eur=None,
            median_days_to_close=None,
            break_even_hammer_eur=required_hammer,
        )

    prices = [float(price) for price in hammer_prices]
    p25 = percentile(prices, 0.25)
    p50 = percentile(prices, 0.50)
    p75 = percentile(prices, 0.75)
    net_min = net_proceeds(p25, cost_eur, settings)
    net_avg = net_proceeds(p50, cost_eur, settings)
    net_max = net_proceeds(p75, cost_eur, settings)

    return PriceQuote(
        verdict=decide(net_min, net_avg, threshold),
        sample_size=len(prices),
        attempt_count=attempts,
        sell_through_rate=sell_through,
        cost_eur=cost_eur,
        threshold_eur=threshold,
        net_min_eur=net_min,
        net_avg_eur=net_avg,
        net_max_eur=net_max,
        hammer_p25_eur=p25,
        hammer_median_eur=p50,
        hammer_p75_eur=p75,
        median_days_to_close=percentile([float(day) for day in days_to_close], 0.50),
        break_even_hammer_eur=required_hammer,
    )
