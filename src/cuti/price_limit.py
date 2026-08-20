"""Maximum purchase cost derived from an evaluated comparable pool."""

from __future__ import annotations

from .config import Settings
from .models import Verdict
from .pricing import PriceQuote, decide, net_proceeds, profit_threshold, vnd_to_eur


def max_buy_cost_vnd(price: PriceQuote, settings: Settings) -> int | None:
    """Return the greatest integer VND cost that keeps the p25 green.

    The quote already contains the pool's p25 hammer.  Candidate costs are
    checked through the pricing primitives and the same strict ``decide``
    boundary used by normal quotes.  A thin pool, or a pool with no usable p25,
    cannot produce a purchase limit.
    """
    if price.sample_size < settings.min_comparables or price.hammer_p25_eur is None:
        return None

    def is_green(cost_vnd: int) -> bool:
        cost_eur = vnd_to_eur(cost_vnd, settings)
        threshold = profit_threshold(cost_eur, settings)
        net_p25 = net_proceeds(price.hammer_p25_eur, cost_eur, settings)
        return decide(net_p25, net_p25, threshold) is Verdict.GREEN

    if not is_green(1):
        return None

    low = 1
    high = 1
    while is_green(high):
        low = high
        high *= 2
    while low + 1 < high:
        middle = (low + high) // 2
        if is_green(middle):
            low = middle
        else:
            high = middle
    return low
