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
