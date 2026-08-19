"""Command line entry point for CUTI-Tools."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from typing import Sequence

from .cli_commands import execute
from .cli_output import emit as _emit
from .cli_parser import _parse_day, build_parser
from .config import BUSINESS_TIMEZONE, load_settings
from .errors import CutiError
from .liquidity import compute_liquidity
from .models import Condition, WatchForm
from .normalize import load_rules
from .notifier import build_notifier
from .pipeline import (
    check_source_urls,
    ingest_lots,
    ingest_one_lot,
    quote_watch,
    settle_lots,
    watch_deals,
    watch_live,
)
from .report import write_report
from .storage import connect, count_rows, fetch_quote_audit, outbox_counts

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    now = datetime.now(timezone.utc)
    today = args.today or now.astimezone(BUSINESS_TIMEZONE).date()
    settings = load_settings(base_dir=args.home)
    rules = load_rules(settings.rules_path)
    operations = {
        "check_source_urls": check_source_urls,
        "compute_liquidity": compute_liquidity,
        "count_rows": count_rows,
        "fetch_quote_audit": fetch_quote_audit,
        "ingest_lots": ingest_lots,
        "ingest_one_lot": ingest_one_lot,
        "quote_watch": quote_watch,
        "settle_lots": settle_lots,
        "watch_deals": watch_deals,
        "watch_live": watch_live,
        "build_notifier": build_notifier,
        "outbox_counts": outbox_counts,
        "write_report": write_report,
    }
    with connect(settings.db_path) as conn:
        return execute(args, conn, rules, settings, today, now, _emit, operations)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(argv)
    except CutiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except argparse.ArgumentError as exc:  # pragma: no cover
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
