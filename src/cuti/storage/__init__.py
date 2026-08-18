"""Public SQLite storage facade.

The package keeps the historical ``cuti.storage`` import path while separating
schema/migration code from focused query modules.
"""

from .deals import StoredDeal, fetch_unquoted_deals, insert_deal_if_new
from .lots import (
    fetch_lots_for_liquidity,
    fetch_lots_for_model,
    fetch_sold_lots_since,
    search_sold_lots,
    upsert_lots,
)
from .quotes import (
    ComparableSnapshot,
    PendingAlert,
    claim_pending_alerts,
    count_rows,
    fetch_quote_audit,
    insert_quote,
    mark_alert_failed,
    mark_alert_sent,
    outbox_counts,
)
from .schema import LOT_COLUMNS_AFTER_V1, NO, SCHEMA_VERSION, SCHEMA_SQL, YES, connect
from .watch import (
    LiveWatchRow,
    count_live_watch,
    delete_live_watch,
    fetch_live_watch_due,
    fetch_lots_for_source_check,
    mark_source_availability,
    upsert_live_watch,
)

__all__ = [
    "SCHEMA_VERSION",
    "SCHEMA_SQL",
    "LOT_COLUMNS_AFTER_V1",
    "YES",
    "NO",
    "connect",
    "upsert_lots",
    "fetch_lots_for_model",
    "fetch_lots_for_liquidity",
    "fetch_sold_lots_since",
    "search_sold_lots",
    "StoredDeal",
    "insert_deal_if_new",
    "fetch_unquoted_deals",
    "ComparableSnapshot",
    "insert_quote",
    "PendingAlert",
    "claim_pending_alerts",
    "mark_alert_sent",
    "mark_alert_failed",
    "outbox_counts",
    "count_rows",
    "fetch_quote_audit",
    "LiveWatchRow",
    "upsert_live_watch",
    "fetch_live_watch_due",
    "delete_live_watch",
    "count_live_watch",
    "fetch_lots_for_source_check",
    "mark_source_availability",
]
