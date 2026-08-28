"""Public SQLite storage facade.

The package keeps the historical ``cuti.storage`` import path while separating
schema/migration code from focused query modules.
"""

from .deals import StoredDeal, fetch_unquoted_deals, insert_deal_if_new
from .freshness import DataFreshness, assess_data_freshness
from .catalog import CanonicalProduct, ensure_catalog, fetch_product, load_catalog, search_products
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
from .schema_migration import ensure_media_queue, rollback_frontend_schema
from .watch import (
    LiveWatchRow,
    count_live_watch,
    delete_live_watch,
    fetch_live_watch_due,
    fetch_lots_for_source_check,
    mark_source_availability,
    upsert_live_watch,
    upsert_live_watch_with_images,
)
from .media import (claim_lot_image, count_lot_images, fetch_lot_image, fetch_lot_images,
                    find_lot_ids_missing_cover, find_lots_missing_cover,
                    mark_lot_image_failed, mark_lot_image_ready, upsert_lot_image)
from .user_items import (
    TrackedDeal,
    create_tracked_deal,
    fetch_tracked_deal,
    list_saved_products,
    list_tracked_deals,
    save_product,
    unsave_product,
    update_deal_status,
)

__all__ = [
    "SCHEMA_VERSION",
    "SCHEMA_SQL",
    "LOT_COLUMNS_AFTER_V1",
    "YES",
    "NO",
    "connect",
    "rollback_frontend_schema",
    "ensure_media_queue",
    "DataFreshness",
    "assess_data_freshness",
    "CanonicalProduct", "load_catalog", "ensure_catalog", "fetch_product", "search_products",
    "TrackedDeal", "save_product", "unsave_product", "list_saved_products", "create_tracked_deal",
    "list_tracked_deals", "fetch_tracked_deal", "update_deal_status",
    "upsert_lot_image", "fetch_lot_image", "fetch_lot_images", "count_lot_images",
    "find_lots_missing_cover",
    "find_lot_ids_missing_cover",
    "claim_lot_image", "mark_lot_image_ready", "mark_lot_image_failed",
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
    "upsert_live_watch_with_images",
    "fetch_live_watch_due",
    "delete_live_watch",
    "count_live_watch",
    "fetch_lots_for_source_check",
    "mark_source_availability",
]
