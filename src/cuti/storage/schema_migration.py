"""Derived-index migration helpers for the storage schema."""

import sqlite3


def ensure_fts(conn: sqlite3.Connection) -> None:
    """Keep FTS scoped to title, brand and model, rebuilding v3 indexes."""
    expected = {"title", "brand", "model"}
    current = {row[1] for row in conn.execute("PRAGMA table_info(lots_fts)")}
    if current != expected:
        conn.executescript(
    """
            DROP TRIGGER IF EXISTS lots_ai;
            DROP TRIGGER IF EXISTS lots_ad;
            DROP TRIGGER IF EXISTS lots_au;
            DROP TABLE IF EXISTS lots_fts;
            CREATE VIRTUAL TABLE lots_fts USING fts5(
                title, brand, model, content='lots', content_rowid='rowid'
            );
            INSERT INTO lots_fts(rowid, title, brand, model)
                SELECT rowid, title, brand, model FROM lots;
            """
        )
    else:
        conn.executescript(
            """
            DROP TRIGGER IF EXISTS lots_ai;
            DROP TRIGGER IF EXISTS lots_ad;
            DROP TRIGGER IF EXISTS lots_au;
            """
        )
    conn.executescript(
        """
        CREATE TRIGGER lots_ai AFTER INSERT ON lots BEGIN
            INSERT INTO lots_fts(rowid, title, brand, model)
            VALUES (new.rowid, new.title, new.brand, new.model);
        END;
        CREATE TRIGGER lots_ad AFTER DELETE ON lots BEGIN
            INSERT INTO lots_fts(lots_fts, rowid, title, brand, model)
            VALUES ('delete', old.rowid, old.title, old.brand, old.model);
        END;
        CREATE TRIGGER lots_au AFTER UPDATE ON lots BEGIN
            INSERT INTO lots_fts(lots_fts, rowid, title, brand, model)
            VALUES ('delete', old.rowid, old.title, old.brand, old.model);
            INSERT INTO lots_fts(rowid, title, brand, model)
            VALUES (new.rowid, new.title, new.brand, new.model);
        END;
        """
    )


MEDIA_QUEUE_COLUMNS = (
    ("state", "TEXT NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'uploading', 'ready', 'retryable_error', 'permanent_error'))"),
    ("attempts", "INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0)"),
    ("last_error", "TEXT"),
    ("next_attempt_at", "TEXT"),
    ("lease_owner", "TEXT"),
    ("lease_expires_at", "TEXT"),
)


def ensure_media_queue(conn: sqlite3.Connection) -> None:
    """Add durable media queue fields to a pre-queue database."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(lot_images)")}
    for name, definition in MEDIA_QUEUE_COLUMNS:
        if name not in columns:
            conn.execute(f"ALTER TABLE lot_images ADD COLUMN {name} {definition}")
    conn.execute(
        """UPDATE lot_images
           SET state = 'ready', next_attempt_at = NULL,
               lease_owner = NULL, lease_expires_at = NULL
           WHERE telegram_file_id IS NOT NULL AND state <> 'ready'"""
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_lot_images_queue
           ON lot_images(state, next_attempt_at, lease_expires_at, lot_id, idx)"""
    )


def rollback_frontend_schema(conn: sqlite3.Connection) -> None:
    """Remove only the additive frontend tables from an explicit DB copy."""
    with conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS tracked_deals;
            DROP TABLE IF EXISTS saved_products;
            DROP TABLE IF EXISTS product_aliases;
            DROP TABLE IF EXISTS canonical_products;
            """
        )
