"""Command line entry point.

One thin adapter over :mod:`cuti.pipeline`: parse arguments, build settings,
run a use case, print a deterministic summary. Exit code 0 on success, 1 on any
typed :class:`CutiError`, 2 on bad usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence

from .config import BUSINESS_TIMEZONE, load_settings
from .errors import CutiError
from .liquidity import compute_liquidity
from .models import Condition, WatchForm
from .normalize import load_rules
from .notifier import build_notifier
from .pipeline import ingest_lots, quote_watch, watch_deals
from .report import write_report
from .storage import count_rows, fetch_quote_audit, open_db, outbox_counts

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


def _parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cuti", description="CUTI-Tools watch arbitrage MVP")
    parser.add_argument("--home", type=Path, default=None, help="project root (default: CUTI_HOME or cwd)")
    parser.add_argument("--today", type=_parse_day, default=None, help="override 'today' (YYYY-MM-DD)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="create the SQLite schema")
    sub.add_parser("ingest", help="crawl the auction source into SQLite")

    quote_cmd = sub.add_parser("quote", help="price one watch against comparables")
    quote_cmd.add_argument("--title", required=True)
    quote_cmd.add_argument("--cost-vnd", required=True, type=int)
    quote_cmd.add_argument(
        "--condition",
        choices=[item.value for item in Condition],
        required=True,
        help="explicit condition cluster",
    )
    quote_cmd.add_argument(
        "--form",
        choices=[item.value for item in WatchForm],
        default=WatchForm.UNKNOWN.value,
        help="case form (default: unknown)",
    )

    sub.add_parser("watch", help="ingest the VN deal feed and alert on green lights")
    sub.add_parser("liquidity", help="rank brands by liquidity index")
    sub.add_parser("report", help="write the static HTML report")
    sub.add_parser("status", help="show row counts and effective configuration")
    audit_cmd = sub.add_parser("audit", help="show an immutable quote snapshot")
    audit_cmd.add_argument("--quote-id", required=True, type=int)
    return parser


def _emit(payload: dict[str, object], as_json: bool, lines: Sequence[str]) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print("\n".join(lines))


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    today = args.today or now.astimezone(BUSINESS_TIMEZONE).date()
    settings = load_settings(base_dir=args.home)
    rules = load_rules(settings.rules_path)

    with open_db(settings.db_path) as conn:
        if args.command == "init-db":
            _emit(
                {"db_path": str(settings.db_path), "status": "ready"},
                args.json,
                [f"Database ready at {settings.db_path}"],
            )
        elif args.command == "ingest":
            report = ingest_lots(conn, rules, settings, now)
            _emit(
                {
                    "pages_fetched": report.pages_fetched,
                    "lots_written": report.lots_written,
                    "stopped_reason": report.stopped_reason,
                    "lots_total": count_rows(conn, "lots"),
                },
                args.json,
                [
                    f"Pages fetched : {report.pages_fetched}",
                    f"Lots written  : {report.lots_written}",
                    f"Lots in db    : {count_rows(conn, 'lots')}",
                    f"Stopped       : {report.stopped_reason}",
                ],
            )
        elif args.command == "quote":
            report = quote_watch(
                conn,
                rules,
                settings,
                title=args.title,
                cost_vnd=args.cost_vnd,
                condition=Condition(args.condition),
                form=WatchForm(args.form),
                today=today,
                now=now,
            )
            price = report.price
            _emit(
                {
                    "title": report.title,
                    "model_key": report.model_key,
                    "condition": report.condition.value,
                    "form": report.form.value,
                    "verdict": price.verdict.value,
                    "sample_size": price.sample_size,
                    "attempt_count": price.attempt_count,
                    "sell_through_rate": price.sell_through_rate,
                    "cost_eur": round(price.cost_eur, 2),
                    "threshold_eur": round(price.threshold_eur, 2),
                    "net_min_eur": price.net_min_eur,
                    "net_avg_eur": price.net_avg_eur,
                    "net_max_eur": price.net_max_eur,
                    "median_days_to_close": price.median_days_to_close,
                    "break_even_hammer_eur": price.break_even_hammer_eur,
                    "quote_id": report.quote_id,
                },
                args.json,
                [
                    f"Model      : {report.model_key} ({report.condition.value}/{report.form.value})",
                    f"Verdict    : {price.verdict.value.upper()}",
                    f"Sample     : {price.sample_size}/{price.attempt_count} sold/attempts",
                    f"Cost       : {price.cost_eur:,.0f} EUR",
                    f"Threshold  : {price.threshold_eur:,.0f} EUR",
                    "Net p25/med/p75: "
                    + (
                        "n/a"
                        if price.net_min_eur is None
                        else f"{price.net_min_eur:,.0f} / {price.net_avg_eur:,.0f} / "
                        f"{price.net_max_eur:,.0f} EUR"
                    ),
                ],
            )
        elif args.command == "watch":
            notifier = build_notifier(settings)
            report = watch_deals(conn, rules, settings, notifier, today=today, now=now)
            _emit(
                {
                    "deals_seen": report.deals_seen,
                    "deals_new": report.deals_new,
                    "deals_stale": report.deals_stale,
                    "deals_quoted": report.deals_quoted,
                    "alerts_sent": report.alerts_sent,
                    "alerts_failed": report.alerts_failed,
                    "outbox_pending": report.outbox_pending,
                    "outbox_dead": report.outbox_dead,
                    "errors": report.errors,
                    "verdicts": [
                        {"title": title, "verdict": verdict.value}
                        for title, verdict in report.verdicts
                    ],
                },
                args.json,
                [
                    f"Deals seen : {report.deals_seen}",
                    f"Deals new  : {report.deals_new}",
                    f"Deals stale: {report.deals_stale}",
                    f"Quoted     : {report.deals_quoted}",
                    f"Alerts     : {report.alerts_sent} sent / {report.alerts_failed} failed",
                    f"Outbox     : {report.outbox_pending} pending / {report.outbox_dead} dead",
                    *[f"Error      : {error}" for error in report.errors],
                    *[
                        f"  - [{verdict.value}] {title}"
                        for title, verdict in report.verdicts
                    ],
                ],
            )
            if report.errors:
                return EXIT_ERROR
        elif args.command == "liquidity":
            report = compute_liquidity(conn, settings, today)
            _emit(
                {
                    "window_start": report.window_start,
                    "window_end": report.window_end,
                    "brands": [
                        {
                            "brand": item.brand,
                            "form": item.form.value,
                            "lots": item.lots,
                            "sold": item.sold,
                            "sell_through": round(item.sell_through, 4),
                            "median_days_to_close": item.median_days_to_close,
                            "heart_to_hammer": round(item.heart_to_hammer, 4),
                            "index": round(item.index, 4),
                            "latest_qoq_change": item.latest_qoq_change,
                            "stop_buying": item.stop_buying,
                        }
                        for item in report.brands
                    ],
                    "excluded_groups": [
                        {"brand": brand, "form": form.value, "lots": lots}
                        for brand, form, lots in report.excluded_groups
                    ],
                },
                args.json,
                [
                    f"{'brand/form':<28}{'lots':>6}{'sold':>6}{'sell%':>8}{'days':>8}{'index':>8}{'qoq':>8}",
                    *[
                        f"{(item.brand + '/' + item.form.value):<28}{item.lots:>6}{item.sold:>6}"
                        f"{item.sell_through * 100:>7.0f}%"
                        + (
                            f"{'-':>8}"
                            if item.median_days_to_close is None
                            else f"{item.median_days_to_close:>8.1f}"
                        )
                        + f"{item.index:>8.3f}"
                        + (f"{'-':>8}" if item.latest_qoq_change is None else f"{item.latest_qoq_change:>8.0%}")
                        for item in report.brands
                    ],
                ],
            )
        elif args.command == "report":
            path = write_report(conn, settings, today)
            _emit({"report_path": str(path)}, args.json, [f"Report written to {path}"])
        elif args.command == "status":
            payload = {
                "base_dir": str(settings.base_dir),
                "db_path": str(settings.db_path),
                "lots": count_rows(conn, "lots"),
                "deals": count_rows(conn, "deals"),
                "quotes": count_rows(conn, "quotes"),
                "quote_comparables": count_rows(conn, "quote_comparables"),
                "alert_outbox": outbox_counts(conn),
                "notifier": settings.notifier,
                "min_comparables": settings.min_comparables,
                "match_threshold": settings.match_threshold,
            }
            _emit(payload, args.json, [f"{key:<16}: {value}" for key, value in payload.items()])
        elif args.command == "audit":
            payload = fetch_quote_audit(conn, args.quote_id)
            _emit(payload, True, [])
        else:  # pragma: no cover - argparse guarantees a known command
            parser.error(f"unknown command {args.command!r}")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(argv)
    except CutiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except argparse.ArgumentError as exc:  # pragma: no cover - argparse exits itself
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
