"""Single-user saved products and tracked-deal persistence."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from ..errors import StorageError
from ..models import Condition
from .catalog import CanonicalProduct, _row_to_product
from .schema import utcnow


@dataclass(frozen=True, slots=True)
class TrackedDeal:
    id: int
    product: CanonicalProduct
    ask_amount: float
    currency: str
    condition: Condition
    status: str
    snapshot: dict[str, object]
    created_at: str
    updated_at: str


def save_product(conn: sqlite3.Connection, product_id: str, now: datetime) -> bool:
    with conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO saved_products(product_id, created_at) VALUES (?, ?)",
            (product_id, utcnow(now)),
        )
    return cursor.rowcount == 1


def unsave_product(conn: sqlite3.Connection, product_id: str) -> bool:
    with conn:
        cursor = conn.execute("DELETE FROM saved_products WHERE product_id = ?", (product_id,))
    return cursor.rowcount == 1


def list_saved_products(conn: sqlite3.Connection) -> list[CanonicalProduct]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT p.* FROM canonical_products p JOIN saved_products s ON s.product_id = p.product_id
           ORDER BY s.created_at, p.product_id"""
    ).fetchall()
    return [_row_to_product(row) for row in rows]


def _deal_row(row: sqlite3.Row) -> TrackedDeal:
    return TrackedDeal(
        id=row["id"], product=_row_to_product(row), ask_amount=row["ask_amount"],
        currency=row["currency"], condition=Condition(row["condition_tag"]), status=row["status"],
        snapshot=json.loads(row["snapshot_json"]), created_at=row["created_at"], updated_at=row["updated_at"],
    )


def create_tracked_deal(
    conn: sqlite3.Connection, *, product_id: str, ask_amount: float, currency: str,
    condition: Condition, snapshot: dict[str, object], now: datetime,
) -> tuple[TrackedDeal, bool]:
    stable = json.dumps({"product_id": product_id, "ask_amount": ask_amount, "currency": currency,
                         "condition": condition.value, "snapshot": snapshot}, sort_keys=True, ensure_ascii=False)
    dedupe_hash = hashlib.sha256(stable.encode("utf-8")).hexdigest()
    timestamp = utcnow(now)
    with conn:
        conn.execute(
            """INSERT OR IGNORE INTO tracked_deals
               (product_id, ask_amount, currency, condition_tag, snapshot_json, dedupe_hash, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (product_id, ask_amount, currency, condition.value, json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
             dedupe_hash, timestamp, timestamp),
        )
        row = conn.execute(
            """SELECT d.*, p.product_id, p.canonical_name, p.brand, p.reference, p.model_key,
                      p.aliases_json, p.provenance FROM tracked_deals d
               JOIN canonical_products p ON p.product_id = d.product_id WHERE d.dedupe_hash = ?""",
            (dedupe_hash,),
        ).fetchone()
    if row is None:
        raise StorageError("tracked deal was not persisted")
    return _deal_row(row), row["created_at"] == timestamp


def list_tracked_deals(conn: sqlite3.Connection, query: str = "") -> list[TrackedDeal]:
    conn.row_factory = sqlite3.Row
    params: list[object] = []
    clause = ""
    if query.strip():
        clause = "AND (p.canonical_name LIKE ? OR p.reference LIKE ?)"
        like = f"%{query.strip()}%"
        params.extend((like, like))
    rows = conn.execute(
        """SELECT d.*, p.product_id, p.canonical_name, p.brand, p.reference, p.model_key,
                  p.aliases_json, p.provenance FROM tracked_deals d
           JOIN canonical_products p ON p.product_id = d.product_id WHERE 1=1 """ + clause
        + " ORDER BY d.updated_at DESC, d.id DESC", params).fetchall()
    return [_deal_row(row) for row in rows]


def fetch_tracked_deal(conn: sqlite3.Connection, deal_id: int) -> TrackedDeal | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """SELECT d.*, p.product_id, p.canonical_name, p.brand, p.reference, p.model_key,
                  p.aliases_json, p.provenance FROM tracked_deals d
           JOIN canonical_products p ON p.product_id = d.product_id WHERE d.id = ?""", (deal_id,)
    ).fetchone()
    return _deal_row(row) if row else None


def update_deal_status(conn: sqlite3.Connection, deal_id: int, status: str, now: datetime) -> TrackedDeal:
    if status not in {"purchased", "skipped"}:
        raise StorageError("deal status must be purchased or skipped")
    with conn:
        cursor = conn.execute(
            "UPDATE tracked_deals SET status = ?, updated_at = ? WHERE id = ? AND status = 'considering'",
            (status, utcnow(now), deal_id),
        )
    deal = fetch_tracked_deal(conn, deal_id)
    if deal is None:
        raise StorageError(f"tracked deal {deal_id} not found")
    if cursor.rowcount != 1 and deal.status != status:
        raise StorageError("deal status transition is not allowed")
    return deal
