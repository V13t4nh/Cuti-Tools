"""T6 schema and pending-review pool regressions."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
import zlib
from datetime import date
from pathlib import Path

from cuti.models import Condition
from cuti.storage import connect, search_sold_lots

from support import NOW, make_lot


class SchemaV4MigrationTests(unittest.TestCase):
    def test_v3_migration_preserves_lot_and_adds_lot_desc(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy-v3.db"
            legacy = sqlite3.connect(path)
            legacy.executescript(
                """
                CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE lots (
                    lot_id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL,
                    brand TEXT NOT NULL, model_key TEXT NOT NULL, condition_tag TEXT NOT NULL,
                    hearts INTEGER NOT NULL, sold INTEGER NOT NULL, hammer_eur INTEGER,
                    opened_at TEXT NOT NULL, ended_at TEXT NOT NULL, url TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE quotes (
                    id INTEGER PRIMARY KEY, deal_id INTEGER, model_key TEXT,
                    assumptions TEXT, created_at TEXT
                );
                INSERT INTO schema_meta VALUES ('version', '3');
                INSERT INTO lots VALUES (
                    'legacy-1', 'catawiki', 'Omega 2849-6 SC', 'omega', 'omega:2849',
                    'naked', 2, 1, 1000, '2026-07-01', '2026-07-02',
                    'https://example.invalid/legacy-1', '2026-07-02T00:00:00+00:00'
                );
                PRAGMA user_version = 3;
                """
            )
            legacy.close()

            conn = connect(path)
            try:
                row = conn.execute(
                    "SELECT title, hammer_eur, ref_number, needs_review, review_status "
                    "FROM lots WHERE lot_id = 'legacy-1'"
                ).fetchone()
                self.assertEqual(row["title"], "Omega 2849-6 SC")
                self.assertEqual(row["hammer_eur"], 1000)
                self.assertIsNone(row["ref_number"])
                self.assertEqual(row["needs_review"], 0)
                self.assertEqual(row["review_status"], "pending")
                self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 4)
                self.assertIsNotNone(
                    conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lot_desc'"
                    ).fetchone()
                )
            finally:
                conn.close()

    def test_lot_desc_round_trip_is_zlib_and_keeps_blob_out_of_lots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            conn = connect(Path(directory) / "desc.db")
            try:
                description = "Vintage Omega Cal. 503 — signed dial and steel case."
                encoded = zlib.compress(description.encode("utf-8"))
                conn.execute(
                    "INSERT INTO lot_desc(lot_id, desc_z) VALUES (?, ?)",
                    ("lot-1", encoded),
                )
                row = conn.execute(
                    "SELECT desc_z FROM lot_desc WHERE lot_id = 'lot-1'"
                ).fetchone()
                self.assertEqual(zlib.decompress(row["desc_z"]).decode("utf-8"), description)
                self.assertNotIn("desc_z", {item[1] for item in conn.execute("PRAGMA table_info(lots)")})
            finally:
                conn.close()


class PendingReviewPoolTests(unittest.TestCase):
    def test_pending_review_lot_is_excluded_from_sold_pool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            conn = connect(Path(directory) / "pool.db")
            try:
                conn.execute("PRAGMA foreign_keys = ON")
                for lot in (
                    make_lot("clean-1", ended_at=date(2026, 7, 1)),
                    make_lot("pending-1", ended_at=date(2026, 7, 2)),
                ):
                    conn.execute(
                        """INSERT INTO lots (
                            lot_id, source, title, brand, model_key, condition_tag,
                            form, hearts, sold, hammer_eur, opened_at, ended_at, url,
                            updated_at, needs_review, review_status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            lot.lot_id, lot.source, lot.title, lot.brand, lot.model_key,
                            lot.condition_tag.value, lot.form.value, lot.hearts, int(lot.sold),
                            lot.hammer_eur, lot.opened_at.isoformat(), lot.ended_at.isoformat(),
                            lot.url, NOW.isoformat(), int(lot.lot_id.startswith("pending")),
                            "pending",
                        ),
                    )
                rows = search_sold_lots(
                    conn,
                    fts_query='"omega" OR "210.30.42"',
                    brand="omega",
                    model_key="omega:210.30.42",
                    condition_tag=Condition.NAKED,
                    since=date(2020, 1, 1),
                )
                self.assertEqual([lot.lot_id for lot in rows], ["clean-1"])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
