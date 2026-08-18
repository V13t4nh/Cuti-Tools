"""Linear application workflows for ingesting, pricing and alerting."""

from __future__ import annotations

import hashlib
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

from .comparables import find_comparables
from .config import Settings
from .errors import NormalizationError, ScrapeError
from .fetch import fetch_json, fetch_text, probe_url, resolve, to_url
from .models import Condition, Deal, Lot, Verdict, WatchForm
from .normalize import Rules, classify
from .notifier import Notifier
from .pricing import PriceQuote, quote
from .scrapers import catawiki, catawiki_api, deals as deals_scraper
from .storage import (
    ComparableSnapshot,
    LiveWatchRow,
    claim_pending_alerts,
    delete_live_watch,
    fetch_live_watch_due,
    fetch_lots_for_source_check,
    fetch_unquoted_deals,
    insert_deal_if_new,
    insert_quote,
    mark_alert_failed,
    mark_alert_sent,
    mark_source_availability,
    count_live_watch,
    outbox_counts,
    upsert_live_watch,
    upsert_lots,
)

@dataclass(frozen=True, slots=True)
class IngestReport:
    pages_fetched: int
    lots_written: int
    stopped_reason: str

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

def _local_path(url: str) -> Path:
    parsed = urlparse(url)
    path = unquote(parsed.path)
    if len(path) >= 3 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    return Path(path).resolve()

def _safe_next_url(root_url: str, current_url: str, next_href: str) -> str:
    """Resolve pagination without allowing a feed to leave its source origin."""
    candidate = resolve(current_url, next_href)
    root = urlparse(root_url)
    target = urlparse(candidate)
    if (root.scheme, root.netloc) != (target.scheme, target.netloc):
        raise ScrapeError(f"pagination left the configured source origin: {candidate}")
    if root.scheme == "file" and not _local_path(candidate).is_relative_to(
        _local_path(root_url).parent
    ):
        raise ScrapeError(f"pagination left the configured source directory: {candidate}")
    return candidate

def ingest_lots(
    conn: sqlite3.Connection, rules: Rules, settings: Settings, now: datetime
) -> IngestReport:
    """Preflight every source page, then atomically store the normalized crawl."""
    root_url = to_url(settings.lots_source_url)
    url = root_url
    visited: set[str] = set()
    seen_lot_ids: set[str] = set()
    lots: list[Lot] = []
    pages = 0
    reason = "no next page"

    while True:
        if url in visited:
            raise ScrapeError(f"pagination loop detected at {url}")
        visited.add(url)
        page = catawiki.parse_listing(
            fetch_text(
                url,
                settings.http_timeout_seconds,
                max_bytes=settings.response_max_bytes,
            )
        )
        pages += 1
        for raw in page.lots:
            if raw.lot_id in seen_lot_ids:
                raise ScrapeError(f"duplicate lot_id across source pages: {raw.lot_id}")
            seen_lot_ids.add(raw.lot_id)
            classification = classify(raw.title, rules)
            if (
                classification.condition is not None
                and classification.condition is not raw.condition
            ):
                raise ScrapeError(
                    f"{raw.lot_id}: title condition conflicts with data-condition"
                )
            lots.append(
                Lot(
                    lot_id=raw.lot_id,
                    source=catawiki.SOURCE_NAME,
                    title=raw.title,
                    brand=classification.brand,
                    model_key=classification.model_key,
                    condition_tag=raw.condition,
                    form=raw.form,
                    hearts=raw.hearts,
                    sold=raw.sold,
                    hammer_eur=raw.hammer_eur,
                    opened_at=raw.opened_at,
                    ended_at=raw.ended_at,
                    url=resolve(url, raw.url),
                )
            )

        if page.next_href is None:
            break
        if pages >= settings.source_max_pages:
            reason = "page limit reached"
            break
        url = _safe_next_url(root_url, url, page.next_href)

    return IngestReport(
        pages_fetched=pages,
        lots_written=upsert_lots(conn, lots, now),
        stopped_reason=reason,
    )

def _rules_fingerprint(settings: Settings) -> str:
    try:
        payload = settings.rules_path.read_bytes()
    except OSError as exc:
        raise ScrapeError(f"cannot fingerprint rules file {settings.rules_path}: {exc}") from exc
    return hashlib.sha256(payload).hexdigest()

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
        conn,
        title=title,
        condition=effective_condition,
        rules=rules,
        settings=settings,
        today=today,
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
            deal,
            model_key=classification.model_key,
            condition=effective_condition,
            form=form,
            price=price,
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

def _drain_alerts(
    conn: sqlite3.Connection,
    notifier: Notifier,
    settings: Settings,
    now: datetime,
) -> tuple[int, int, list[str]]:
    sent = 0
    failed = 0
    errors: list[str] = []
    for alert in claim_pending_alerts(conn, now):
        try:
            notifier.send(alert.payload)
        except Exception as exc:  # delivery implementations may expose library-specific errors
            failed += 1
            message = f"alert {alert.id} delivery failed: {exc}"
            errors.append(message)
            mark_alert_failed(
                conn,
                alert.id,
                str(exc),
                max_attempts=settings.alert_max_attempts,
            )
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

        # The whole external batch is validated before the first database write.
        prepared: list[Deal] = []
        stale = 0
        earliest = today - timedelta(days=settings.deal_max_age_days)
        for raw in raw_deals:
            classification = classify(raw.title, rules)
            if (
                classification.condition is not None
                and classification.condition is not raw.condition
            ):
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

        new_count = sum(
            insert_deal_if_new(conn, deal, now) is not None for deal in prepared
        )

        quoted = 0
        verdicts: list[tuple[str, Verdict]] = []
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

    alerts_sent, alerts_failed, delivery_errors = _drain_alerts(
        conn, notifier, settings, now
    )
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
        "net_median_eur": (
            round(price.net_median_eur, 2) if price.net_median_eur is not None else None
        ),
        "threshold_eur": round(price.threshold_eur, 2),
        "break_even_hammer_eur": round(price.break_even_hammer_eur, 2),
        "median_days_to_close": price.median_days_to_close,
    }

# --- Live auction capture -------------------------------------------------
#
# The auction source cannot be searched for closed lots, so a hammer price can
# only be collected in two phases: capture ids while bidding is open
# (`watch_live`), then read the final result after bidding ends (`settle_lots`).
# `check_source_urls` records whether a stored lot page can still be opened, so
# a price that can no longer be verified is flagged instead of silently trusted.

@dataclass(frozen=True, slots=True)
class WatchLiveReport:
    queries: tuple[str, ...]
    pages_fetched: int
    lots_seen: int
    lots_tracked: int
    lots_refreshed: int
    windows_unknown: int
    requests_made: int

@dataclass(frozen=True, slots=True)
class SettleReport:
    candidates: int
    sold: int
    unsold: int
    still_open: int
    vanished: int
    unclassified: int
    lots_written: int
    queue_remaining: int
    requests_made: int

@dataclass(frozen=True, slots=True)
class SourceCheckReport:
    checked: int
    alive: int
    dead: int

@dataclass(slots=True)
class _Settlement:
    """Working result of one settle pass, before anything is written."""

    lots: list[Lot]
    finished: list[str]
    refreshed: list[LiveWatchRow]
    sold: int = 0
    unsold: int = 0
    still_open: int = 0
    vanished: int = 0
    unclassified: int = 0

def _catawiki_client(
    settings: Settings, api: catawiki_api.CatawikiApi | None = None
) -> catawiki_api.CatawikiApi:
    if api is not None:
        return api
    return catawiki_api.CatawikiApi(
        api_base=settings.catawiki_api_base,
        timeout_seconds=settings.http_timeout_seconds,
        max_bytes=settings.response_max_bytes,
        pause_seconds=settings.catawiki_pause_seconds,
    )

def watch_live(
    conn: sqlite3.Connection,
    settings: Settings,
    now: datetime,
    *,
    api: catawiki_api.CatawikiApi | None = None,
) -> WatchLiveReport:
    """Phase 1: record every lot that is open right now, with its close date."""
    client = _catawiki_client(settings, api)
    refs: dict[str, catawiki_api.LotRef] = {}
    pages = 0
    for query in settings.catawiki_queries:
        for page_number in range(1, settings.catawiki_search_max_pages + 1):
            page = client.search(query, page_number)
            pages += 1
            if not page.lots:
                break
            for ref in page.lots:
                # One lot can match several queries; first sighting wins.
                refs.setdefault(ref.lot_id, ref)

    # Search results carry no end time, so the window comes from a batched
    # live-state lookup. A lot that closed while we were paging keeps an unknown
    # window and is therefore due immediately.
    windows: dict[str, date] = {}
    for batch in catawiki_api.chunks(list(refs), settings.catawiki_batch_size):
        for lot_id, state in client.live_states(batch).items():
            if not state.closed:
                windows[lot_id] = state.ended_at

    rows = [
        LiveWatchRow(
            lot_id=lot_id,
            source=catawiki_api.SOURCE_NAME,
            title=ref.title,
            subtitle=ref.subtitle,
            url=ref.url,
            bidding_end_at=windows.get(lot_id),
        )
        for lot_id, ref in refs.items()
    ]
    tracked, refreshed = upsert_live_watch(conn, rows, now)
    return WatchLiveReport(
        queries=settings.catawiki_queries,
        pages_fetched=pages,
        lots_seen=len(rows),
        lots_tracked=tracked,
        lots_refreshed=refreshed,
        windows_unknown=sum(1 for row in rows if row.bidding_end_at is None),
        requests_made=client.requests_made,
    )

def _settled_lot(
    row: LiveWatchRow,
    state: catawiki_api.LiveState,
    outcome: catawiki_api.BiddingOutcome,
    rules: Rules,
) -> Lot:
    """Turn a closed lot into a storable record, or raise NormalizationError.

    `form` stays UNKNOWN because the buyer JSON never states the case shape;
    guessing it would poison the brand/form liquidity index.
    """
    classification = classify(row.title, rules)
    if classification.condition is None:
        raise NormalizationError(f"{row.lot_id}: title states no condition")
    return Lot(
        lot_id=row.lot_id,
        source=row.source,
        title=row.title,
        brand=classification.brand,
        model_key=classification.model_key,
        condition_tag=classification.condition,
        form=WatchForm.UNKNOWN,
        hearts=state.favorite_count,
        sold=outcome.is_sold,
        hammer_eur=outcome.hammer_eur,
        opened_at=state.opened_at,
        ended_at=state.ended_at,
        url=row.url,
        subtitle=row.subtitle,
        bids_count=outcome.bids_count,
    )

def _settle(
    client: catawiki_api.CatawikiApi,
    rules: Rules,
    settings: Settings,
    candidates: list[LiveWatchRow],
) -> _Settlement:
    """Read the final state of every candidate without writing anything."""
    by_id = {row.lot_id: row for row in candidates}
    result = _Settlement(lots=[], finished=[], refreshed=[])
    for batch in catawiki_api.chunks(list(by_id), settings.catawiki_batch_size):
        states = client.live_states(batch)
        for lot_id in batch:
            row = by_id[lot_id]
            state = states.get(lot_id)
            if state is None:
                # The source forgot the lot before we could settle it. Nothing
                # can be recovered, so stop asking for it.
                result.vanished += 1
                result.finished.append(lot_id)
                continue
            if not state.closed:
                # Bidding was extended. Re-queue with the new end date.
                result.still_open += 1
                result.refreshed.append(
                    LiveWatchRow(
                        lot_id=row.lot_id,
                        source=row.source,
                        title=row.title,
                        subtitle=row.subtitle,
                        url=row.url,
                        bidding_end_at=state.ended_at,
                    )
                )
                continue
            outcome = client.outcome(lot_id)
            if not outcome.is_closed:
                result.still_open += 1
                continue
            try:
                lot = _settled_lot(row, state, outcome, rules)
            except NormalizationError:
                # Unlike `ingest_lots`, a live crawl must not abort on one
                # unparseable title: the source is not a curated fixture. The
                # lot is dropped from the queue and counted, never guessed.
                result.unclassified += 1
                result.finished.append(lot_id)
                continue
            result.lots.append(lot)
            result.finished.append(lot_id)
            if outcome.is_sold:
                result.sold += 1
            else:
                result.unsold += 1
    return result

def _persist_settlement(
    conn: sqlite3.Connection, settlement: _Settlement, now: datetime
) -> int:
    written = upsert_lots(conn, settlement.lots, now)
    if settlement.refreshed:
        upsert_live_watch(conn, settlement.refreshed, now)
    delete_live_watch(conn, settlement.finished)
    return written

def settle_lots(
    conn: sqlite3.Connection,
    rules: Rules,
    settings: Settings,
    today: date,
    now: datetime,
    *,
    api: catawiki_api.CatawikiApi | None = None,
) -> SettleReport:
    """Phase 2: read the hammer price of every tracked lot that has closed."""
    client = _catawiki_client(settings, api)
    candidates = fetch_live_watch_due(conn, until=today, limit=settings.settle_max_lots)
    settlement = _settle(client, rules, settings, candidates)
    written = _persist_settlement(conn, settlement, now)
    return SettleReport(
        candidates=len(candidates),
        sold=settlement.sold,
        unsold=settlement.unsold,
        still_open=settlement.still_open,
        vanished=settlement.vanished,
        unclassified=settlement.unclassified,
        lots_written=written,
        queue_remaining=count_live_watch(conn),
        requests_made=client.requests_made,
    )

def ingest_one_lot(
    conn: sqlite3.Connection,
    rules: Rules,
    settings: Settings,
    today: date,
    now: datetime,
    *,
    url: str,
    api: catawiki_api.CatawikiApi | None = None,
) -> SettleReport:
    """Track a single lot URL and settle it immediately if bidding has ended."""
    client = _catawiki_client(settings, api)
    lot_id = catawiki_api.lot_id_from_url(url)
    titles = client.titles([lot_id])
    if lot_id not in titles:
        raise ScrapeError(f"lot {lot_id} is no longer readable at the source")
    known = titles[lot_id]
    row = LiveWatchRow(
        lot_id=lot_id,
        source=catawiki_api.SOURCE_NAME,
        title=known.title,
        subtitle=None,
        url=known.url,
        bidding_end_at=None,
    )
    upsert_live_watch(conn, [row], now)
    settlement = _settle(client, rules, settings, [row])
    written = _persist_settlement(conn, settlement, now)
    return SettleReport(
        candidates=1,
        sold=settlement.sold,
        unsold=settlement.unsold,
        still_open=settlement.still_open,
        vanished=settlement.vanished,
        unclassified=settlement.unclassified,
        lots_written=written,
        queue_remaining=count_live_watch(conn),
        requests_made=client.requests_made,
    )

def check_source_urls(
    conn: sqlite3.Connection,
    settings: Settings,
    now: datetime,
    *,
    probe: object = None,
) -> SourceCheckReport:
    """Flag stored lots whose source page can no longer be opened.

    A page counts as alive only when it answers 200 *and* still resolves to the
    same lot: an expired lot is redirected to a category page, which would
    otherwise look like a healthy 200.
    """
    probe_fn = probe or probe_url
    candidates = fetch_lots_for_source_check(conn, limit=settings.url_check_max_lots)
    results: dict[str, bool] = {}
    for index, (lot_id, url) in enumerate(candidates):
        if index and settings.catawiki_pause_seconds > 0:
            time.sleep(settings.catawiki_pause_seconds)
        status, final_url = probe_fn(url, settings.http_timeout_seconds)
        results[lot_id] = status == 200 and f"/l/{lot_id}" in final_url
    mark_source_availability(conn, results, now)
    alive = sum(1 for ok in results.values() if ok)
    return SourceCheckReport(
        checked=len(results), alive=alive, dead=len(results) - alive
    )
