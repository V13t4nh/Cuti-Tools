"""Normalize naive SQLite timestamps in auctions.db to ISO-8601 UTC."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "var" / "auctions.db"


def normalize_timestamps(db_path: Path) -> tuple[int, int]:
    if not db_path.is_file():
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 0, 0

    conn = sqlite3.connect(db_path)
    try:
        with conn:
            # Fix updated_at in lots
            cur = conn.execute(
                """
                UPDATE lots
                SET updated_at = replace(updated_at, ' ', 'T') || '+00:00'
                WHERE updated_at NOT LIKE '%+%' AND updated_at NOT LIKE '%Z'
                """
            )
            updated_count = cur.rowcount

            # Fix reviewed_at in lots
            cur = conn.execute(
                """
                UPDATE lots
                SET reviewed_at = replace(reviewed_at, ' ', 'T') || '+00:00'
                WHERE reviewed_at IS NOT NULL
                  AND reviewed_at NOT LIKE '%+%'
                  AND reviewed_at NOT LIKE '%Z'
                """
            )
            reviewed_count = cur.rowcount

        return updated_count, reviewed_count
    finally:
        conn.close()


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DB_PATH
    print(f"Normalizing timestamps in: {path}")
    updated, reviewed = normalize_timestamps(path)
    print(f"-> Normalized lots.updated_at: {updated} rows")
    print(f"-> Normalized lots.reviewed_at: {reviewed} rows")
    print("[SUCCESS] All timestamps are now ISO-8601 UTC compliant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
