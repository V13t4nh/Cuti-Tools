"""Vietnam deal-feed watch and notification workflow."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ..config import Settings
from ..errors import ScrapeError
from ..fetch import fetch_json
from ..models import Condition, Deal, Verdict
from ..normalize import Rules, classify
from ..notifier import Notifier
from ..scrapers import deals as deals_scraper
from ..storage import (
    claim_pending_alerts,
    fetch_unquoted_deals,
    insert_deal_if_new,
    mark_alert_failed,
    mark_alert_sent,
    outbox_counts,
)


@dataclass(frozen=True, slots=True)
class WatchReport:
    deals_seen: int
    deals_new: int
    deals_stale: int
    deals_quoted: int
    alerts_sent: int
    alerts_failed: int
    outbox_pending: int
    outbox_dead: int
    verdicts: tuple[tuple[str, Verdict], ...]
    errors: tuple[str, ...]


def _drain_alerts(
    conn: sqlite3.Connection, notifier: Notifier, settings: Settings, now: datetime
) -> tuple[int, int, list[str]]:
    sent = failed = 0
    errors: list[str] = []
    for alert in claim_pending_alerts(conn, now):
        try:
            notifier.send(alert.payload)
        except Exception as exc:  # delivery implementations may expose library-specific errors
            failed += 1
            message = f"alert {alert.id} delivery failed: {exc}"
            errors.append(message)
            mark_alert_failed(conn, alert.id, str(exc), max_attempts=settings.alert_max_attempts)
        else:
            mark_alert_sent(conn, alert.id, now)
            sent += 1
    return sent, failed, errors


def watch_deals(
    conn: sqlite3.Connection,
    rules: Rules,
    settings: Settings,
    notifier: Notifier,
    *,
    today: date,
    now: datetime,
) -> WatchReport:
    """Preflight a deal batch, quote all eligible unquoted deals, then drain alerts."""
    try:
        raw_deals = deals_scraper.parse_feed(
            fetch_json(
                settings.deals_source_url,
                settings.http_timeout_seconds,
                max_bytes=settings.response_max_bytes,
            )
        )
        prepared: list[Deal] = []
        stale = 0
        earliest = today - timedelta(days=settings.deal_max_age_days)
        for raw in raw_deals:
            classification = classify(raw.title, rules)
            if classification.condition is not None and classification.condition is not raw.condition:
                raise ScrapeError(f"deal condition conflicts with title: {raw.title!r}")
            if raw.seen_at < earliest or raw.seen_at > today:
                stale += 1
                continue
            prepared.append(
                Deal(
                    source=raw.source,
                    raw_title=raw.title,
                    ask_vnd=raw.ask_vnd,
                    url=raw.url,
                    seen_at=raw.seen_at,
                    model_key=classification.model_key,
                    condition_tag=raw.condition,
                    form=raw.form,
                    dedupe_hash=raw.dedupe_hash,
                )
            )
        new_count = sum(insert_deal_if_new(conn, deal, now) is not None for deal in prepared)
        quoted = 0
        verdicts: list[tuple[str, Verdict]] = []
        # Resolve through the facade so existing callers can patch cuti.pipeline.quote_watch.
        from . import quote_watch

        for stored in fetch_unquoted_deals(conn, since=earliest, until=today):
            deal = stored.deal
            report = quote_watch(
                conn,
                rules,
                settings,
                title=deal.raw_title,
                cost_vnd=deal.ask_vnd,
                condition=deal.condition_tag,
                form=deal.form,
                today=today,
                now=now,
                deal=deal,
                deal_id=stored.id,
            )
            quoted += 1
            verdicts.append((deal.raw_title, report.price.verdict))
    except Exception as exc:
        try:
            _, _, delivery_errors = _drain_alerts(conn, notifier, settings, now)
        except Exception as drain_exc:
            exc.add_note(f"outbox drain also failed: {drain_exc}")
        else:
            if delivery_errors:
                exc.add_note("outbox delivery errors: " + "; ".join(delivery_errors))
        raise

    alerts_sent, alerts_failed, delivery_errors = _drain_alerts(conn, notifier, settings, now)
    counts = outbox_counts(conn)
    return WatchReport(
        deals_seen=len(raw_deals),
        deals_new=new_count,
        deals_stale=stale,
        deals_quoted=quoted,
        alerts_sent=alerts_sent,
        alerts_failed=alerts_failed,
        outbox_pending=counts["pending"] + counts["sending"],
        outbox_dead=counts["dead"],
        verdicts=tuple(verdicts),
        errors=tuple(delivery_errors),
    )
