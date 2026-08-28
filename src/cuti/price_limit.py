"""Maximum purchase cost derived from an evaluated comparable pool."""

from __future__ import annotations

from .config import Settings
from .errors import PricingError
from .models import Verdict
from .pricing import quote


def max_buy_cost_vnd(
    hammers: list[int], days_to_close: list[int], settings: Settings
) -> int | None:
    """Return the greatest integer VND cost that keeps the pool green.

    Every candidate is checked through the public pricing quote, so this
    boundary stays identical to the normal deal decision.  A thin pool cannot
    produce a purchase limit.
    """
    if len(hammers) < settings.min_comparables:
        return None

    def is_green(cost_vnd: int) -> bool:
        return quote(hammers, days_to_close, cost_vnd, settings).verdict is Verdict.GREEN

    if not is_green(1):
        return None

    low = 1
    high = 1
    for _ in range(63):
        if not is_green(high):
            break
        low = high
        high *= 2
    else:
        raise PricingError("max_buy_cost search did not find a finite boundary")
    while low + 1 < high:
        middle = (low + high) // 2
        if is_green(middle):
            low = middle
        else:
            high = middle
    return low
