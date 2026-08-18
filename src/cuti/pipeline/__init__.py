"""Public facade for the application's linear workflows.

The implementation is organized by command, while these imports preserve the
historic ``cuti.pipeline`` API used by the CLI and downstream callers.
"""

from .ingest import IngestReport, ingest_lots
from .quote import QuoteReport, quote_watch
from .report import (
    SettleReport,
    SourceCheckReport,
    WatchLiveReport,
    check_source_urls,
    ingest_one_lot,
    settle_lots,
    watch_live,
)
from .watch import WatchReport, watch_deals

__all__ = [
    "IngestReport",
    "QuoteReport",
    "SettleReport",
    "SourceCheckReport",
    "WatchLiveReport",
    "WatchReport",
    "check_source_urls",
    "ingest_lots",
    "ingest_one_lot",
    "quote_watch",
    "settle_lots",
    "watch_deals",
    "watch_live",
]
