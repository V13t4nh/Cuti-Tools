"""Migrate lot model_key in SQLite database from pipe format to canonical colon format.

Safe migration script with pre/post verification and transaction safety.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "var" / "auctions.db"


def migrate(db_path: Path, dry_run: bool = False) -> None:
    print(f"Opening database: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Pre-check stats
    cur.execute("SELECT count(*) FROM lots")
    total_lots = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM lots WHERE instr(model_key, '|') > 0")
    pipe_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM lots WHERE instr(model_key, ':') > 0")
    colon_count = cur.fetchone()[0]

    print("--- PRE-MIGRATION STATS ---")
    print(f"Total lots:           {total_lots}")
    print(f"Lots with pipe (|):   {pipe_count}")
    print(f"Lots with colon (:):  {colon_count}")

    if pipe_count == 0:
        print("No lots found with pipe (|) in model_key. Nothing to migrate.")
        conn.close()
        return

    # 2. Compute transformations
    cur.execute("SELECT lot_id, model_key FROM lots WHERE instr(model_key, '|') > 0")
    rows = cur.fetchall()
    updates: list[tuple[str, str]] = []
    for lot_id, old_key in rows:
        parts = old_key.split("|")
        prefix = parts[0].strip()
        rest = [p.strip() for p in parts[1:] if p.strip()]
        new_key = f"{prefix}:{'-'.join(rest)}"
        updates.append((new_key, lot_id))

    print("\n--- SAMPLE CONVERSIONS (First 5) ---")
    for i in range(min(5, len(updates))):
        print(f"  {rows[i][1]:<35} -> {updates[i][0]}")

    if dry_run:
        print("\n[DRY RUN] No changes were written to database.")
        conn.close()
        return

    # 3. Apply updates in transaction
    print(f"\nApplying {len(updates)} updates...")
    with conn:
        conn.executemany("UPDATE lots SET model_key = ? WHERE lot_id = ?", updates)

    # 4. Post-check stats
    cur.execute("SELECT count(*) FROM lots WHERE instr(model_key, '|') > 0")
    post_pipe = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM lots WHERE instr(model_key, ':') > 0")
    post_colon = cur.fetchone()[0]

    print("\n--- POST-MIGRATION STATS ---")
    print(f"Lots with pipe (|):   {post_pipe} (expected: 0)")
    print(f"Lots with colon (:):  {post_colon} (expected: {total_lots})")

    assert post_pipe == 0, f"Error: Still found {post_pipe} lots with pipe"
    assert post_colon == total_lots, f"Error: Expected {total_lots} lots with colon, got {post_colon}"

    # 5. Top models check
    print("\n--- TOP CLASSIFIED MODELS (Post-migration) ---")
    cur.execute("""
        SELECT model_key, condition_tag, count(*) as cnt, sum(sold) as sold_cnt
        FROM lots
        WHERE needs_review = 0 AND model_key NOT LIKE '%:unclassified'
        GROUP BY model_key, condition_tag
        HAVING sold_cnt >= 5
        ORDER BY sold_cnt DESC
        LIMIT 10
    """)
    for r in cur.fetchall():
        print(f"  {r[0]:<35} | cond={r[1]:<8} | total={r[2]:<3} | sold={r[3]:<3}")

    conn.close()
    print("\nMigration completed successfully!")


if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = Path(args[0]) if args else DEFAULT_DB_PATH
    migrate(target, dry_run=is_dry)
