"""One-watch pricing and immutable quote snapshot workflow."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

from ..comparables import find_comparables
from ..config import Settings
from ..errors import ScrapeError
from ..models import Condition, Deal, WatchForm
from ..normalize import Rules, classify
from ..pricing import PriceQuote, quote
from ..storage import ComparableSnapshot, insert_quote


@dataclass(frozen=True, slots=True)
class QuoteReport:
    title: str
    model_key: str
    condition: Condition
    form: WatchForm
    cost_vnd: int
    price: PriceQuote
    comparable_titles: tuple[str, ...]
    quote_id: int


def _rules_fingerprint(settings: Settings) -> str:
    try:
        payload = settings.rules_path.read_bytes()
    except OSError as exc:
        raise ScrapeError(f"cannot fingerprint rules file {settings.rules_path}: {exc}") from exc
    return hashlib.sha256(payload).hexdigest()


def _alert_payload(
    deal: Deal,
    *,
    model_key: str,
    condition: Condition,
    form: WatchForm,
    price: PriceQuote,
) -> dict[str, object]:
    return {
        "title": deal.raw_title,
        "url": deal.url,
        "source": deal.source,
        "model_key": model_key,
        "condition": condition.value,
        "form": form.value,
        "ask_vnd": deal.ask_vnd,
        "verdict": price.verdict.value,
        "sample_size": price.sample_size,
        "attempt_count": price.attempt_count,
        "sell_through_rate": round(price.sell_through_rate, 4),
        "net_p25_eur": round(price.net_p25_eur, 2) if price.net_p25_eur is not None else None,
        "net_median_eur": round(price.net_median_eur, 2) if price.net_median_eur is not None else None,
        "threshold_eur": round(price.threshold_eur, 2),
        "break_even_hammer_eur": round(price.break_even_hammer_eur, 2),
        "median_days_to_close": price.median_days_to_close,
    }


def quote_watch(
    conn: sqlite3.Connection,
    rules: Rules,
    settings: Settings,
    *,
    title: str,
    cost_vnd: int,
    condition: Condition | None,
    today: date,
    now: datetime,
    form: WatchForm = WatchForm.UNKNOWN,
    deal: Deal | None = None,
    deal_id: int | None = None,
) -> QuoteReport:
    """Price one watch and persist an immutable, replayable decision snapshot."""
    if (deal is None) != (deal_id is None):
        raise ScrapeError("deal and deal_id must be supplied together")
    classification = classify(title, rules)
    effective_condition = condition or classification.condition
    if effective_condition is None:
        raise ScrapeError("condition must be explicit when it cannot be inferred from the title")
    matches = find_comparables(
        conn, title=title, condition=effective_condition, rules=rules, settings=settings, today=today
    )
    sold_matches = [match for match in matches if match.lot.sold]
    hammers = [match.lot.hammer_eur for match in sold_matches]
    if any(value is None for value in hammers):
        raise ScrapeError("a sold comparable is missing its hammer price")
    price = quote(
        [int(value) for value in hammers if value is not None],
        [match.lot.days_to_close for match in sold_matches],
        cost_vnd,
        settings,
        attempt_count=len(matches),
    )
    alert_payload = None
    if deal is not None and price.is_actionable:
        alert_payload = _alert_payload(
            deal, model_key=classification.model_key, condition=effective_condition, form=form, price=price
        )
    assumptions = {
        "audit_version": 2,
        "today": today.isoformat(),
        "comparable_window_days": settings.comparable_window_days,
        "match_threshold": settings.match_threshold,
        "min_comparables": settings.min_comparables,
        "commission_rate": settings.commission_rate,
        "vat_on_commission_rate": settings.vat_on_commission_rate,
        "shipping_eur": settings.shipping_eur,
        "eur_vnd_rate": settings.eur_vnd_rate,
        "min_margin_rate": settings.min_margin_rate,
        "min_profit_eur": settings.min_profit_eur,
        "rules_sha256": _rules_fingerprint(settings),
    }
    quote_id = insert_quote(
        conn,
        model_key=classification.model_key,
        condition_tag=effective_condition,
        form=form,
        title=title,
        cost_vnd=cost_vnd,
        sample_size=price.sample_size,
        attempt_count=price.attempt_count,
        sell_through_rate=price.sell_through_rate,
        net_min_eur=price.net_min_eur,
        net_avg_eur=price.net_avg_eur,
        net_max_eur=price.net_max_eur,
        hammer_p25_eur=price.hammer_p25_eur,
        hammer_median_eur=price.hammer_median_eur,
        hammer_p75_eur=price.hammer_p75_eur,
        median_days_to_close=price.median_days_to_close,
        threshold_eur=price.threshold_eur,
        verdict=price.verdict.value,
        assumptions=assumptions,
        comparables=(ComparableSnapshot(item.lot, item.score) for item in matches),
        deal_id=deal_id,
        alert_payload=alert_payload,
        now=now,
    )
    return QuoteReport(
        title=title,
        model_key=classification.model_key,
        condition=effective_condition,
        form=form,
        cost_vnd=cost_vnd,
        price=price,
        comparable_titles=tuple(match.lot.title for match in matches),
        quote_id=quote_id,
    )
