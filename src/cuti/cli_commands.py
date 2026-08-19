"""Command execution and presentation for the CUTI CLI."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from typing import Callable, Mapping

from .evaluation import cost_to_eur
from .models import Condition, WatchForm


def _evaluation_payload(result: object) -> dict[str, object]:
    """Serialize the pure evaluator without coupling it to a UI."""
    return {
        "query": result.query,
        "model_key": result.model_key,
        "condition": result.condition.value,
        "cost_eur": result.cost_eur,
        "verdict": result.verdict.value,
        "reason": result.reason,
        "sample_size": result.sample_size,
        "attempt_count": result.attempt_count,
        "liquidity_index": result.liquidity_index,
        "liquidity_sell_through": result.liquidity_sell_through,
        "net_p25_eur": result.net_p25_eur,
        "net_median_eur": result.net_median_eur,
        "net_p75_eur": result.net_p75_eur,
        "net_profit_p25_eur": result.net_profit_p25_eur,
        "net_profit_median_eur": result.net_profit_median_eur,
        "net_profit_p75_eur": result.net_profit_p75_eur,
        "threshold_eur": result.threshold_eur,
        "median_days_to_close": result.median_days_to_close,
    }


def execute(
    args: SimpleNamespace,
    conn: object,
    rules: object,
    settings: object,
    today: date,
    now: datetime,
    emit: Callable[[dict[str, object], bool, list[str]], None],
    operations: Mapping[str, Callable[..., object]],
) -> int:
    """Run one parsed command; operations are injected to retain CLI patch points."""
    count_rows = operations["count_rows"]
    if args.command == "init-db":
        emit({"db_path": str(settings.db_path), "status": "ready"}, args.json, [f"Database ready at {settings.db_path}"])
    elif args.command == "ingest":
        report = operations["ingest_lots"](conn, rules, settings, now)
        total = count_rows(conn, "lots")
        emit(
            {"pages_fetched": report.pages_fetched, "lots_written": report.lots_written, "stopped_reason": report.stopped_reason, "lots_total": total},
            args.json,
            [f"Pages fetched : {report.pages_fetched}", f"Lots written  : {report.lots_written}", f"Lots in db    : {total}", f"Stopped       : {report.stopped_reason}"],
        )
    elif args.command == "watch-live":
        live = operations["watch_live"](conn, settings, now)
        queue_total = count_rows(conn, "live_watch")
        emit(
            {"queries": list(live.queries), "pages_fetched": live.pages_fetched, "lots_seen": live.lots_seen, "lots_tracked": live.lots_tracked, "lots_refreshed": live.lots_refreshed, "windows_unknown": live.windows_unknown, "requests_made": live.requests_made, "queue_total": queue_total},
            args.json,
            [f"Queries       : {', '.join(live.queries)}", f"Pages fetched : {live.pages_fetched}", f"Lots seen     : {live.lots_seen}", f"Newly queued  : {live.lots_tracked}", f"Refreshed     : {live.lots_refreshed}", f"Unknown end   : {live.windows_unknown}", f"Requests      : {live.requests_made}", f"Queue total   : {queue_total}"],
        )
    elif args.command in {"settle", "ingest-lot"}:
        if args.command == "settle":
            settled = operations["settle_lots"](conn, rules, settings, today, now)
        else:
            settled = operations["ingest_one_lot"](conn, rules, settings, today, now, url=args.url)
        emit(
            {"candidates": settled.candidates, "sold": settled.sold, "unsold": settled.unsold, "still_open": settled.still_open, "vanished": settled.vanished, "unclassified": settled.unclassified, "lots_written": settled.lots_written, "queue_remaining": settled.queue_remaining, "requests_made": settled.requests_made, "lots_total": count_rows(conn, "lots")},
            args.json,
            [f"Candidates    : {settled.candidates}", f"Sold          : {settled.sold}", f"Unsold        : {settled.unsold}", f"Still open    : {settled.still_open}", f"Vanished      : {settled.vanished}", f"Unclassified  : {settled.unclassified}", f"Lots written  : {settled.lots_written}", f"Queue left    : {settled.queue_remaining}", f"Requests      : {settled.requests_made}"],
        )
    elif args.command == "check-urls":
        checked = operations["check_source_urls"](conn, settings, now)
        emit({"checked": checked.checked, "alive": checked.alive, "dead": checked.dead}, args.json, [f"Checked       : {checked.checked}", f"Still alive   : {checked.alive}", f"Expired       : {checked.dead}"])
    elif args.command == "quote":
        report = operations["quote_watch"](conn, rules, settings, title=args.title, cost_vnd=args.cost_vnd, condition=Condition(args.condition), form=WatchForm(args.form), today=today, now=now)
        price = report.price
        emit(
            {"title": report.title, "model_key": report.model_key, "condition": report.condition.value, "form": report.form.value, "verdict": price.verdict.value, "sample_size": price.sample_size, "attempt_count": price.attempt_count, "sell_through_rate": price.sell_through_rate, "cost_eur": round(price.cost_eur, 2), "threshold_eur": round(price.threshold_eur, 2), "net_min_eur": price.net_min_eur, "net_avg_eur": price.net_avg_eur, "net_max_eur": price.net_max_eur, "median_days_to_close": price.median_days_to_close, "break_even_hammer_eur": price.break_even_hammer_eur, "quote_id": report.quote_id},
            args.json,
            [f"Model    : {report.model_key} ({report.condition.value}/{report.form.value})", f"Verdict  : {price.verdict.value.upper()}", f"Sample   : {price.sample_size}/{price.attempt_count} sold/attempts", f"Cost     : {price.cost_eur:,.0f} EUR", f"Threshold: {price.threshold_eur:,.0f} EUR", "Net p25/med/p75: " + ("n/a" if price.net_min_eur is None else f"{price.net_min_eur:,.0f} / {price.net_avg_eur:,.0f} / {price.net_max_eur:,.0f} EUR")],
        )
    elif args.command == "evaluate":
        result = operations["evaluate_deal"](
            conn,
            rules,
            settings,
            query=args.query,
            cost_eur=cost_to_eur(args.cost, args.currency, settings),
            condition=Condition(args.condition),
            today=today,
        )
        emit(_evaluation_payload(result), True, [])
    elif args.command == "watch":
        notifier = operations["build_notifier"](settings)
        report = operations["watch_deals"](conn, rules, settings, notifier, today=today, now=now)
        emit(
            {"deals_seen": report.deals_seen, "deals_new": report.deals_new, "deals_stale": report.deals_stale, "deals_quoted": report.deals_quoted, "alerts_sent": report.alerts_sent, "alerts_failed": report.alerts_failed, "outbox_pending": report.outbox_pending, "outbox_dead": report.outbox_dead, "errors": report.errors, "verdicts": [{"title": title, "verdict": verdict.value} for title, verdict in report.verdicts]},
            args.json,
            [f"Deals seen : {report.deals_seen}", f"Deals new  : {report.deals_new}", f"Deals stale: {report.deals_stale}", f"Quoted     : {report.deals_quoted}", f"Alerts     : {report.alerts_sent} sent / {report.alerts_failed} failed", f"Outbox     : {report.outbox_pending} pending / {report.outbox_dead} dead", *[f"Error      : {error}" for error in report.errors], *[f"  - [{verdict.value}] {title}" for title, verdict in report.verdicts]],
        )
        if report.errors:
            return 1
    elif args.command == "liquidity":
        report = operations["compute_liquidity"](conn, settings, today)
        rows = [{"brand": item.brand, "form": item.form.value, "lots": item.lots, "sold": item.sold, "sell_through": round(item.sell_through, 4), "median_days_to_close": item.median_days_to_close, "heart_to_hammer": round(item.heart_to_hammer, 4), "index": round(item.index, 4), "latest_qoq_change": item.latest_qoq_change, "stop_buying": item.stop_buying} for item in report.brands]
        lines = [f"{'brand/form':<28}{'lots':>6}{'sold':>6}{'sell%':>8}{'days':>8}{'index':>8}{'qoq':>8}"]
        lines.extend(f"{item.brand + '/' + item.form.value:<28}{item.lots:>6}{item.sold:>6}{item.sell_through * 100:>7.0f}%" + (f"{'-':>8}" if item.median_days_to_close is None else f"{item.median_days_to_close:>8.1f}") + f"{item.index:>8.3f}" + (f"{'-':>8}" if item.latest_qoq_change is None else f"{item.latest_qoq_change:>8.0%}") for item in report.brands)
        emit({"window_start": report.window_start, "window_end": report.window_end, "brands": rows, "excluded_groups": [{"brand": brand, "form": form.value, "lots": lots} for brand, form, lots in report.excluded_groups]}, args.json, lines)
    elif args.command == "report":
        path = operations["write_report"](conn, settings, today)
        emit({"report_path": str(path)}, args.json, [f"Report written to {path}"])
    elif args.command == "status":
        payload = {"base_dir": str(settings.base_dir), "db_path": str(settings.db_path), "lots": count_rows(conn, "lots"), "live_watch": count_rows(conn, "live_watch"), "deals": count_rows(conn, "deals"), "quotes": count_rows(conn, "quotes"), "quote_comparables": count_rows(conn, "quote_comparables"), "alert_outbox": operations["outbox_counts"](conn), "notifier": settings.notifier, "min_comparables": settings.min_comparables, "match_threshold": settings.match_threshold}
        emit(payload, args.json, [f"{key:<16}: {value}" for key, value in payload.items()])
    elif args.command == "audit":
        emit(operations["fetch_quote_audit"](conn, args.quote_id), True, [])
    else:  # pragma: no cover
        raise ValueError(f"unknown command {args.command!r}")
    return 0
