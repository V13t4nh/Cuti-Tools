"""Canonical product catalog and deterministic product search."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from ..errors import StorageError
from ..normalize_rules import normalize_text
from .schema import utcnow


@dataclass(frozen=True, slots=True)
class CanonicalProduct:
    product_id: str
    canonical_name: str
    brand: str
    reference: str
    model_key: str
    aliases: tuple[str, ...]
    provenance: str


def load_catalog(path: Path) -> tuple[CanonicalProduct, ...]:
    """Load the canonical catalog config; malformed data fails at startup."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageError(f"cannot load canonical catalog {path}: {exc}") from exc
    if not isinstance(raw, list):
        raise StorageError("canonical catalog must be a JSON array")
    products: list[CanonicalProduct] = []
    for item in raw:
        if not isinstance(item, dict):
            raise StorageError("canonical catalog entries must be objects")
        required = ("product_id", "canonical_name", "brand", "reference", "model_key")
        if any(not isinstance(item.get(key), str) or not item[key].strip() for key in required):
            raise StorageError("canonical catalog entry is missing a required string")
        aliases = item.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(alias, str) for alias in aliases):
            raise StorageError(f"{item['product_id']}: aliases must be a string array")
        products.append(CanonicalProduct(
            product_id=item["product_id"], canonical_name=item["canonical_name"],
            brand=item["brand"], reference=item["reference"], model_key=item["model_key"],
            aliases=tuple(aliases), provenance=str(item.get("provenance", "config/catalog.json")),
        ))
    return tuple(products)


def ensure_catalog(conn: sqlite3.Connection, products: tuple[CanonicalProduct, ...], now) -> None:
    """Upsert configured products and aliases without deriving identity from lots."""
    timestamp = utcnow(now)
    with conn:
        for product in products:
            conn.execute(
                """INSERT INTO canonical_products
                   (product_id, canonical_name, brand, reference, model_key, aliases_json, provenance, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(product_id) DO UPDATE SET canonical_name=excluded.canonical_name,
                   brand=excluded.brand, reference=excluded.reference, model_key=excluded.model_key,
                   aliases_json=excluded.aliases_json, provenance=excluded.provenance, updated_at=excluded.updated_at""",
                (product.product_id, product.canonical_name, product.brand, product.reference,
                 product.model_key, json.dumps(product.aliases, ensure_ascii=False), product.provenance, timestamp),
            )


def _row_to_product(row: sqlite3.Row) -> CanonicalProduct:
    return CanonicalProduct(
        product_id=row["product_id"], canonical_name=row["canonical_name"], brand=row["brand"],
        reference=row["reference"], model_key=row["model_key"],
        aliases=tuple(json.loads(row["aliases_json"])), provenance=row["provenance"],
    )


def fetch_product(conn: sqlite3.Connection, product_id: str) -> CanonicalProduct | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM canonical_products WHERE product_id = ?", (product_id,)).fetchone()
    return _row_to_product(row) if row else None


def search_products(conn: sqlite3.Connection, query: str, limit: int = 10) -> list[CanonicalProduct]:
    """Rank exact reference first, then exact names/aliases, then fuzzy names."""
    normalized = normalize_text(query)
    if not normalized:
        return []
    query_has_digits = any(char.isdigit() for char in normalized)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM canonical_products ORDER BY product_id").fetchall()
    ranked: list[tuple[float, str, CanonicalProduct]] = []
    for row in rows:
        product = _row_to_product(row)
        ref = normalize_text(product.reference)
        names = [normalize_text(product.canonical_name), *(normalize_text(alias) for alias in product.aliases)]
        if query_has_digits and normalized != ref and any(char.isdigit() for char in ref):
            if normalized not in names and normalized not in ref.split():
                continue
        if normalized == ref:
            score = 1000.0
        elif normalized in names:
            score = 900.0
        elif any(normalized in name for name in names):
            score = 800.0
        else:
            score = max(SequenceMatcher(None, normalized, name).ratio() for name in names) * 100.0
            if score < 30.0:
                continue
        ranked.append((score, product.product_id, product))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked[:limit]]
