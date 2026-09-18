"""Backfill legacy lots.ai_json into lot_refinements table for Schema v6."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "var" / "auctions.db"


def parse_and_flatten_refinement(ai_json_str: str) -> str:
    """Ensure JSON is valid and identity/specs facets are flattened to top-level."""
    data = json.loads(ai_json_str)
    if not isinstance(data, dict):
        raise ValueError("ai_json is not an object")

    identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    specs = data.get("specs") if isinstance(data.get("specs"), dict) else {}
    payload = dict(data)
    for field, value in {
        "brand": identity.get("brand"),
        "model": identity.get("model"),
        "ref_number": identity.get("ref_number"),
        "caliber": identity.get("caliber"),
        "case_code": identity.get("case_code"),
        "movement": specs.get("movement"),
        "case_material": specs.get("case_material"),
        "case_diameter_mm": specs.get("case_diameter_mm"),
    }.items():
        if value is not None:
            payload[field] = value
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def backfill_refinements(db_path: Path, dry_run: bool = False) -> tuple[int, int, int]:
    """Migrate legacy lots.ai_json to lot_refinements table.

    Returns:
        (total_candidates, inserted_count, skipped_count)
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # 1. Count unrefined before backfill
    cur = conn.cursor()
    cur.execute(
        """SELECT count(*) FROM lot_source_details d
           LEFT JOIN lot_refinements r ON r.lot_id = d.lot_id
           WHERE d.state = 'ready' AND (r.lot_id IS NULL OR r.state <> 'ready' OR r.source_hash <> d.content_hash)"""
    )
    unrefined_before = cur.fetchone()[0]

    # 2. Fetch candidates from lots that have ai_json and matching ready source snapshot
    cur.execute(
        """SELECT l.lot_id, d.content_hash, l.ai_json, coalesce(l.updated_at, datetime('now')) as ts,
                  r.lot_id as existing_refine_id, r.state as existing_state
           FROM lots l
           JOIN lot_source_details d ON d.lot_id = l.lot_id
           LEFT JOIN lot_refinements r ON r.lot_id = l.lot_id
           WHERE l.ai_json IS NOT NULL AND d.state = 'ready'"""
    )
    rows = cur.fetchall()
    total_candidates = len(rows)

    records_to_insert: list[tuple[str, str, str, str]] = []
    skipped_count = 0
    corrupt_count = 0

    for r in rows:
        lot_id = r["lot_id"]
        content_hash = r["content_hash"]
        raw_ai_json = r["ai_json"]
        ts = r["ts"]
        existing_refine_id = r["existing_refine_id"]
        existing_state = r["existing_state"]

        # If already present and ready in lot_refinements, preserve existing
        if existing_refine_id and existing_state == "ready":
            skipped_count += 1
            continue

        try:
            encoded_payload = parse_and_flatten_refinement(raw_ai_json)
        except Exception:
            corrupt_count += 1
            continue

        records_to_insert.append((lot_id, content_hash, encoded_payload, ts))

    print(f"[*] Found {total_candidates:,} lots with existing ai_json.")
    print(f"[*] Already ready in lot_refinements: {skipped_count:,}")
    if corrupt_count > 0:
        print(f"[!] Skipped {corrupt_count} lots with unparseable ai_json.")
    print(f"[*] Prepared for backfill: {len(records_to_insert):,} lots.")

    if dry_run:
        print(f"\n[DRY RUN] Would insert {len(records_to_insert):,} rows into lot_refinements. No changes made.")
        conn.close()
        return total_candidates, 0, skipped_count

    t0 = time.time()
    with conn:
        conn.executemany(
            """INSERT INTO lot_refinements (lot_id, source_hash, ai_json, refined_at, state, last_error)
               VALUES (?, ?, ?, ?, 'ready', NULL)
               ON CONFLICT(lot_id) DO UPDATE SET
                   source_hash = excluded.source_hash,
                   ai_json = excluded.ai_json,
                   refined_at = excluded.refined_at,
                   state = 'ready',
                   last_error = NULL""",
            records_to_insert,
        )
    elapsed = time.time() - t0

    # 3. Count unrefined after backfill
    cur.execute(
        """SELECT count(*) FROM lot_source_details d
           LEFT JOIN lot_refinements r ON r.lot_id = d.lot_id
           WHERE d.state = 'ready' AND (r.lot_id IS NULL OR r.state <> 'ready' OR r.source_hash <> d.content_hash)"""
    )
    unrefined_after = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM lot_refinements WHERE state = 'ready'")
    total_ready_refinements = cur.fetchone()[0]

    conn.close()

    print(f"[+] Successfully backfilled {len(records_to_insert):,} records in {elapsed:.2f}s!")
    print(f"[+] Total ready records in lot_refinements: {total_ready_refinements:,}")
    print(f"[+] Unrefined lots before: {unrefined_before:,} -> after: {unrefined_after:,}")

    return total_candidates, len(records_to_insert), skipped_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill legacy lots.ai_json into lot_refinements (Schema v6)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Inspect candidates without modifying DB")
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"[-] Database file not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    backfill_refinements(args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
