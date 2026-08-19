"""Argument parser for the CUTI command line interface."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .models import Condition, WatchForm


def _parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cuti", description="CUTI-Tools watch arbitrage MVP")
    parser.add_argument(
        "--home", type=Path, default=None, help="project root (default: CUTI_HOME or cwd)"
    )
    parser.add_argument("--today", type=_parse_day, default=None, help="override 'today' (YYYY-MM-DD)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="create the SQLite schema")
    sub.add_parser("ingest", help="crawl the auction source into SQLite")
    sub.add_parser("watch-live", help="queue the lots that are open right now")
    sub.add_parser("settle", help="read the hammer price of queued lots that closed")
    sub.add_parser("check-urls", help="flag stored lots whose source page expired")
    ingest_lot_cmd = sub.add_parser("ingest-lot", help="track and settle a single lot URL")
    ingest_lot_cmd.add_argument("--url", required=True, help="source lot URL")

    details_cmd = sub.add_parser("fetch-lot-details", help="fetch and parse one public lot page")
    details_input = details_cmd.add_mutually_exclusive_group(required=True)
    details_input.add_argument("--url", help="public Catawiki lot URL")
    details_input.add_argument("--lot-id", help="Catawiki lot id")

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
