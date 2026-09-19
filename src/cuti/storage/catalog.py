"""Canonical product catalog and deterministic product search."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from ..errors import StorageError
from ..normalize_rules import normalize_text
from ..search_query import NUMERAL_MAP
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
    if row:
        return _row_to_product(row)
    if product_id.startswith("market:"):
        target_slug = product_id[7:]
        has_lots = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='lots'").fetchone()
        if has_lots:
            for r in conn.execute("SELECT DISTINCT brand, model, ref_number, model_key FROM lots WHERE (model IS NOT NULL AND length(model) >= 2) OR (ref_number IS NOT NULL AND length(ref_number) >= 2)").fetchall():
                b, m, ref = str(r["brand"] or "").strip().lower(), str(r["model"] or "").strip(), str(r["ref_number"] or "").strip()
                ref = "" if re.match(r"^\d{4}-\d{4}$", ref) else ref
                m_key = str(r["model_key"] or "").strip()
                s_ref = re.sub(r"[^a-z0-9]+", "-", f"{b}-{m}-{ref}".lower()).strip("-") if ref else None
                s_mod = re.sub(r"[^a-z0-9]+", "-", f"{b}-{m}".lower()).strip("-") if m else None
                if target_slug in (s_ref, s_mod):
                    base = (m if b in m.lower() else f"{b.title()} {m}") if m else f"{b.title()} {ref}"
                    disp = f"{base} {ref}" if (ref and ref.lower() not in base.lower()) else base
                    f_ref = ref if ref else m
                    f_key = m_key if (m_key and not m_key.endswith(":unclassified")) else f"{b}:{target_slug}"
                    prod = CanonicalProduct(product_id, disp, b, f_ref, f_key, (m, ref) if ref else (m,), "market")
                    try:
                        with conn:
                            conn.execute(
                                "INSERT INTO canonical_products (product_id, canonical_name, brand, reference, model_key, aliases_json, provenance, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(product_id) DO NOTHING",
                                (prod.product_id, prod.canonical_name, prod.brand, prod.reference, prod.model_key, json.dumps(prod.aliases, ensure_ascii=False), prod.provenance, utcnow(datetime.now(timezone.utc))),
                            )
                    except sqlite3.IntegrityError:
                        pass
                    return prod
    return None


def search_products(conn: sqlite3.Connection, query: str, limit: int = 10) -> list[CanonicalProduct]:
    """Rank exact reference first, then exact names/aliases, then prefix/fuzzy names, then market models."""
    normalized = normalize_text(query)
    if not normalized:
        return []
    clean_query = re.sub(r"[\s.-]+", "", normalized)
    query_has_digits = any(char.isdigit() for char in normalized)
    clean_norm = re.sub(r"\b(\d{2})\s*[-]?\s*mm\b", r"\1mm", normalized, flags=re.IGNORECASE)
    query_words = clean_norm.replace("-", " ").split()
    query_spaced = " ".join(query_words)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM canonical_products ORDER BY product_id").fetchall()
    ranked: list[tuple[float, str, CanonicalProduct]] = []
    for row in rows:
        product = _row_to_product(row)
        ref = normalize_text(product.reference)
        clean_ref = re.sub(r"[\s.-]+", "", ref)
        names = [normalize_text(product.canonical_name), *(normalize_text(alias) for alias in product.aliases)]
        is_exact_ref = (clean_query == clean_ref) or (normalized == ref)
        ref_in_query = bool(clean_ref and clean_ref in clean_query)
        if query_has_digits and not is_exact_ref and not ref_in_query:
            if not any(query_spaced in name or normalized in name for name in names):
                continue
        if is_exact_ref:
            score = 1000.0
        elif normalized in names or query_spaced in names:
            score = 900.0
        elif any(normalized in name or query_spaced in name for name in names) or ref_in_query:
            score = 800.0
        elif all(any(nw.startswith(qw) for nw in names[0].split()) for qw in query_words):
            score = 750.0
        else:
            best_ratios = []
            for name in names:
                name_words = name.split()
                w_scores = [max(SequenceMatcher(None, qw, nw).ratio() for nw in name_words) for qw in query_words]
                best_ratios.append(sum(w_scores) / len(w_scores) if w_scores else 0.0)
            best_fuzzy = max(best_ratios) if best_ratios else 0.0
            if best_fuzzy >= 0.75:
                score = 700.0 * best_fuzzy
            else:
                score = max(SequenceMatcher(None, query_spaced, name).ratio() for name in names) * 100.0
                if score < 30.0:
                    continue
        ranked.append((score, 99999, product.product_id, product))

    seen_ids = {p.product_id for _, _, _, p in ranked}
    seen_names = {normalize_text(p.canonical_name) for _, _, _, p in ranked}

    if len(ranked) < limit and query_words:
        has_lots = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='lots'").fetchone()
        if has_lots:
            cond_parts, sql_params = [], []
            for w in query_words:
                clean_w = w.replace("-", "").replace(" ", "")
                is_compound = (clean_w != w) or (len(clean_w) >= 6) or (any(c.isdigit() for c in clean_w) and any(c.isalpha() for c in clean_w))
                is_diam = clean_w.endswith("mm") and clean_w[:-2].isdigit() and (15 <= int(clean_w[:-2]) <= 65)
                alt_num = NUMERAL_MAP.get(clean_w)
                if is_diam:
                    d_val = clean_w[:-2]
                    cond_parts.append("(case_diameter_mm = ? OR lower(model) LIKE ? OR lower(model) LIKE ?)")
                    sql_params.extend([int(d_val), f"% {d_val}%", f"{d_val}%"])
                elif alt_num:
                    cond_parts.append("(lower(model) LIKE ? OR lower(model) LIKE ? OR lower(model) LIKE ? OR lower(brand) LIKE ?)")
                    sql_params.extend([f"% {clean_w}%", f"% {alt_num}%", f"{clean_w}%", f"{clean_w}%"])
                elif is_compound:
                    cond_parts.append("(lower(model) LIKE ? OR lower(model) LIKE ? OR lower(brand) LIKE ? OR lower(coalesce(ref_number, '')) LIKE ? OR lower(coalesce(ref_number, '')) LIKE ? OR lower(coalesce(model_key, '')) LIKE ? OR instr(replace(replace(lower(coalesce(ref_number, '')), '-', ''), ' ', ''), ?) > 0 OR instr(replace(replace(lower(model), '-', ''), ' ', ''), ?) > 0)")
                    sql_params.extend([f"{w}%", f"% {w}%", f"{w}%", f"{w}%", f"%-{w}%", f"%:{w}%", clean_w, clean_w])
                else:
                    cond_parts.append("(lower(model) LIKE ? OR lower(model) LIKE ? OR lower(model) LIKE ? OR lower(brand) LIKE ? OR lower(coalesce(ref_number, '')) LIKE ? OR lower(coalesce(ref_number, '')) LIKE ? OR lower(coalesce(model_key, '')) LIKE ? OR lower(coalesce(model_key, '')) LIKE ?)")
                    sql_params.extend([f"{w}%", f"% {w}%", f"%-{w}%", f"{w}%", f"{w}%", f"%-{w}%", f"%:{w}%", f"%-{w}%"])
            clause = " AND ".join(cond_parts) if cond_parts else "1"
            lot_rows = conn.execute(
                f"""
                SELECT model, brand, ref_number, model_key, COUNT(*) as cnt
                FROM lots
                WHERE ((model IS NOT NULL AND length(model) >= 2) OR (ref_number IS NOT NULL AND length(ref_number) >= 2))
                AND {clause}
                GROUP BY lower(coalesce(model, '')), lower(brand), lower(coalesce(ref_number, ''))
                ORDER BY cnt DESC, length(model) ASC
                LIMIT ?
                """,
                [*sql_params, (limit - len(ranked)) * 3],
            ).fetchall()
            for r in lot_rows:
                brand_str = str(r["brand"] or "").strip().lower()
                model_str = str(r["model"] or "").strip()
                ref_str = str(r["ref_number"] or "").strip()
                ref_str = "" if re.match(r"^\d{4}-\d{4}$", ref_str) else ref_str
                m_key = str(r["model_key"] or "").strip()
                norm_m, norm_ref = normalize_text(model_str), normalize_text(ref_str)
                if not norm_m and not norm_ref: continue
                base_name = (model_str if brand_str in model_str.lower() else f"{brand_str.title()} {model_str}") if model_str else f"{brand_str.title()} {ref_str}"
                display_name = f"{base_name} {ref_str}" if (ref_str and ref_str.lower() not in base_name.lower()) else base_name
                norm_display = normalize_text(display_name)
                if norm_display in seen_names: continue
                seen_names.add(norm_display)
                if norm_m: seen_names.add(norm_m)
                final_ref = ref_str if ref_str else model_str
                slug = re.sub(r"[^a-z0-9]+", "-", (f"{brand_str}-{model_str}-{ref_str}" if ref_str else f"{brand_str}-{model_str}").lower()).strip("-")
                p_id = f"market:{slug}"
                if p_id in seen_ids: continue
                seen_ids.add(p_id)
                final_model_key = m_key if (m_key and not m_key.endswith(":unclassified")) else f"{brand_str}:{slug}"
                prod = CanonicalProduct(
                    product_id=p_id, canonical_name=display_name, brand=brand_str,
                    reference=final_ref, model_key=final_model_key,
                    aliases=tuple(dict.fromkeys(a for a in (model_str, ref_str, display_name) if a)),
                    provenance="market",
                )
                clean_ref = re.sub(r"[\s.-]+", "", norm_ref)
                score = 950.0 if (clean_query and clean_ref and clean_query == clean_ref) else 600.0
                ranked.append((score, int(r["cnt"]), p_id, prod))
                if len(ranked) >= limit: break

    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [item[3] for item in ranked[:limit]]
