from __future__ import annotations
import json
from datetime import date
from .storage import fetch_lot_image
from .telegram_media import cover_metadata

def extract_quality(specs_data: dict, ai_data: dict | None) -> str | None:
    cond_raw = ""
    if specs_data:
        details = specs_data.get("details") or {}
        cond_val = specs_data.get("Condition") or details.get("Condition") or details.get("condition")
        if isinstance(details, dict) and "details" in details and not cond_val:
            cond_val = details["details"].get("Condition")
        if cond_val:
            cond_raw = str(cond_val).lower()
    if "unworn" in cond_raw or "new" in cond_raw or "mint" in cond_raw:
        return "new_unworn"
    if "very good" in cond_raw or "excellent" in cond_raw:
        return "very_good"
    if "good" in cond_raw or "fine" in cond_raw or "worn" in cond_raw:
        return "good"
    if "fair" in cond_raw or "parts" in cond_raw or "working" in cond_raw:
        return "fair"
    if ai_data and isinstance(ai_data, dict):
        cond_dict = ai_data.get("condition") or {}
        case_c = str(cond_dict.get("case_condition") or "").lower()
        mvt_s = str(cond_dict.get("movement_status") or "").lower()
        if case_c == "unpolished":
            return "very_good"
        if case_c in ("good", "scratched", "polished"):
            return "good"
        if case_c == "dented" or "service" in mvt_s or mvt_s == "not_working":
            return "fair"
    return None

QUALITY_SQL = {
    "new_unworn": "(instr(lower(coalesce(specs_json, '')), '\"condition\": \"new\"') > 0 OR instr(lower(coalesce(specs_json, '')), 'unworn') > 0 OR instr(lower(coalesce(specs_json, '')), 'mint') > 0)",
    "very_good": "(instr(lower(coalesce(specs_json, '')), 'very good') > 0 OR instr(lower(coalesce(specs_json, '')), 'excellent') > 0 OR (instr(lower(coalesce(specs_json, '')), '\"condition\": \"new\"') = 0 AND instr(lower(coalesce(specs_json, '')), 'unworn') = 0 AND instr(lower(coalesce(ai_json, '')), '\"case_condition\": \"unpolished\"') > 0))",
    "good": "(((instr(lower(coalesce(specs_json, '')), '\"condition\": \"good') > 0 OR instr(lower(coalesce(specs_json, '')), '\"condition\": \"fine\"') > 0) AND instr(lower(coalesce(specs_json, '')), 'very good') = 0) OR (instr(lower(coalesce(specs_json, '')), '\"condition\": \"new\"') = 0 AND instr(lower(coalesce(specs_json, '')), 'unworn') = 0 AND instr(lower(coalesce(ai_json, '')), '\"case_condition\": \"good\"') > 0))",
    "fair": "(instr(lower(coalesce(specs_json, '')), 'fair') > 0 OR instr(lower(coalesce(ai_json, '')), '\"case_condition\": \"dented\"') > 0 OR instr(lower(coalesce(ai_json, '')), 'needs_service') > 0 OR instr(lower(coalesce(ai_json, '')), 'not_working') > 0)"
}

def normalize_movement(val: str | None, specs: dict) -> str | None:
    raw = (val or "").strip().lower()
    if not raw and specs:
        raw = str(specs.get("Movement") or specs.get("movement") or "").strip().lower()
    if "auto" in raw:
        return "auto"
    if "manual" in raw or "hand" in raw:
        return "manual"
    if "quartz" in raw:
        return "quartz"
    return val if val in ("auto", "manual", "quartz") else None

def normalize_material(val: str | None, specs: dict) -> str | None:
    raw = (val or "").strip().lower()
    if not raw and specs:
        raw = str(specs.get("Case material") or specs.get("case_material") or "").strip().lower()
    if "plated" in raw or "tone" in raw or "gold_plated" in raw:
        return "gold_plated"
    if "gold" in raw or "yellow gold" in raw or "rose gold" in raw or "white gold" in raw:
        return "gold"
    if "steel" in raw:
        return "steel"
    if "titanium" in raw:
        return "titanium"
    return val if val in ("steel", "gold", "gold_plated", "titanium") else None

def list_auctions(conn, settings, params, pagination_fn, freshness_json_fn, freshness):
    query, wanted = params.get("q", [""])[0].strip().lower(), params.get("status", ["all"])[0].strip().lower()
    today = date.today().isoformat()
    conditions_raw = params.get("conditions", [""])[0].strip().lower()
    qualities_raw = params.get("qualities", [""])[0].strip().lower()
    movements_raw = params.get("movements", [""])[0].strip().lower()
    materials_raw = params.get("materials", [""])[0].strip().lower()
    where, args = [], []
    if query:
        where.append("(instr(lower(coalesce(lot_id, '')), ?) > 0 OR instr(lower(coalesce(title, '')), ?) > 0 OR instr(lower(coalesce(subtitle, '')), ?) > 0)")
        args.extend([query] * 3)
    has_meta_filter = bool(conditions_raw or qualities_raw or movements_raw or materials_raw)
    if wanted == "settled" or (wanted == "all" and has_meta_filter):
        if conditions_raw:
            valid_conds = {"naked", "box", "papers", "fullset"}
            selected_conds = [c.strip() for c in conditions_raw.split(",") if c.strip() in valid_conds]
            if selected_conds:
                placeholders = ",".join("?" for _ in selected_conds)
                where.append(f"condition_tag IN ({placeholders})")
                args.extend(selected_conds)
        if qualities_raw:
            selected_q = [q.strip() for q in qualities_raw.split(",") if q.strip() in QUALITY_SQL]
            if selected_q:
                q_expr = " OR ".join(QUALITY_SQL[q] for q in selected_q)
                where.append(f"({q_expr})")
        if movements_raw:
            selected_m = [m.strip() for m in movements_raw.split(",") if m.strip()]
            if selected_m:
                m_conds = []
                for m in selected_m:
                    if m in ("auto", "automatic"):
                        m_conds.append("(movement = 'auto' OR movement = 'automatic' OR instr(lower(coalesce(specs_json, '')), '\"movement\": \"automatic\"') > 0)")
                    elif m in ("manual", "hand-wound mechanical", "mechanical"):
                        m_conds.append("(movement = 'manual' OR movement LIKE '%manual%' OR instr(lower(coalesce(specs_json, '')), 'manual') > 0)")
                    elif m == "quartz":
                        m_conds.append("(movement = 'quartz' OR instr(lower(coalesce(specs_json, '')), 'quartz') > 0)")
                if m_conds:
                    where.append(f"({' OR '.join(m_conds)})")
        if materials_raw:
            selected_mat = [mat.strip() for mat in materials_raw.split(",") if mat.strip()]
            if selected_mat:
                mat_conds = []
                for mat in selected_mat:
                    if mat in ("steel", "stainless steel"):
                        mat_conds.append("(case_material = 'steel' OR case_material LIKE '%steel%' OR instr(lower(coalesce(specs_json, '')), 'steel') > 0)")
                    elif mat in ("gold", "yellow gold", "rose gold", "white gold"):
                        mat_conds.append("(case_material = 'gold' OR (case_material LIKE '%gold%' AND case_material NOT LIKE '%plated%' AND case_material NOT LIKE '%tone%'))")
                    elif mat in ("gold_plated", "gold plated", "gold_tone", "gold tone"):
                        mat_conds.append("(case_material = 'gold_plated' OR case_material LIKE '%plated%' OR case_material LIKE '%tone%')")
                    elif mat == "titanium":
                        mat_conds.append("(case_material = 'titanium' OR instr(lower(coalesce(specs_json, '')), 'titanium') > 0)")
                if mat_conds:
                    where.append(f"({' OR '.join(mat_conds)})")
        clause = f" WHERE {' AND '.join(where)}" if where else ""
        total = conn.execute(f"SELECT COUNT(*) FROM lots{clause}", args).fetchone()[0]
        offset, pagination = pagination_fn(params, total)
        rows = conn.execute(f"SELECT lot_id, source, title, subtitle, url, ended_at, hammer_eur, sold, bids_count, hearts, needs_review, source_available, review_status, specs_json, condition_tag, ai_json, movement, case_material, case_diameter_mm FROM lots{clause} ORDER BY ended_at DESC, lot_id LIMIT ? OFFSET ?", [*args, pagination["page_size"], offset]).fetchall()
        lots = []
        for r in rows:
            s_obj = json.loads(r["specs_json"]) if r["specs_json"] else {}
            a_obj = json.loads(r["ai_json"]) if "ai_json" in r.keys() and r["ai_json"] else {}
            lots.append({
                "lot_id": r["lot_id"], "source": r["source"], "title": r["title"], "subtitle": r["subtitle"], "url": r["url"],
                "bidding_end_at": r["ended_at"], "status": "settled", "hammer_eur": r["hammer_eur"], "sold": bool(r["sold"]),
                "bids_count": r["bids_count"], "hearts": r["hearts"], "needs_review": r["needs_review"],
                "source_available": r["source_available"] not in ("__NO__", 0, False), "review_status": r["review_status"],
                "condition_tag": r["condition_tag"] if "condition_tag" in r.keys() else None,
                "quality": extract_quality(s_obj, a_obj),
                "movement": normalize_movement(r["movement"] if "movement" in r.keys() else None, s_obj),
                "case_material": normalize_material(r["case_material"] if "case_material" in r.keys() else None, s_obj),
                "case_diameter_mm": r["case_diameter_mm"] if "case_diameter_mm" in r.keys() else None,
                "unclassified_reason": s_obj.get("unclassified_reason"),
                "highest_bid_eur": s_obj.get("highest_bid_eur"),
                "cover": cover_metadata(fetch_lot_image(conn, r["lot_id"]))
            })
        return {"state": "loaded", "data_freshness": freshness_json_fn(freshness), "lots": lots, "pagination": pagination}
    if has_meta_filter:
        where.append("0")
    state_sql = "bidding_end_at IS NOT NULL AND bidding_end_at <> '' AND bidding_end_at > ?"
    if wanted == "open": where.append(state_sql); args.append(today)
    elif wanted == "waiting": where.append(f"NOT ({state_sql})"); args.append(today)
    elif wanted != "all": where.append("0")
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM live_watch{clause}", args).fetchone()[0]
    offset, pagination = pagination_fn(params, total)
    rows = conn.execute(f"SELECT lot_id, source, title, subtitle, url, bidding_end_at FROM live_watch{clause} ORDER BY bidding_end_at, lot_id LIMIT ? OFFSET ?", [*args, pagination["page_size"], offset]).fetchall()
    lots = [{"lot_id": r["lot_id"], "source": r["source"], "title": r["title"], "subtitle": r["subtitle"], "url": r["url"], "bidding_end_at": r["bidding_end_at"], "status": "open" if r["bidding_end_at"] and r["bidding_end_at"] > today else "waiting", "condition_tag": None, "quality": None, "movement": None, "case_material": None, "case_diameter_mm": None, "cover": cover_metadata(fetch_lot_image(conn, r["lot_id"]))} for r in rows]
    return {"state": "loaded", "data_freshness": freshness_json_fn(freshness), "lots": lots, "pagination": pagination}

def get_auction_lot(conn, lot_id: str) -> dict[str, object] | None:
    row = conn.execute("SELECT lot_id, source, title, subtitle, url, bidding_end_at FROM live_watch WHERE lot_id = ?", (lot_id,)).fetchone()
    if row is not None:
        end = row["bidding_end_at"]
        status = "open" if end and end > date.today().isoformat() else "waiting"
        return {"lot_id": row["lot_id"], "source": row["source"], "title": row["title"], "subtitle": row["subtitle"], "url": row["url"], "bidding_end_at": end, "status": status, "condition_tag": None, "quality": None, "movement": None, "case_material": None, "case_diameter_mm": None, "cover": cover_metadata(fetch_lot_image(conn, row["lot_id"]))}
    row = conn.execute("SELECT lot_id, source, title, subtitle, url, ended_at, hammer_eur, sold, bids_count, hearts, needs_review, source_available, review_status, specs_json, condition_tag, ai_json, movement, case_material, case_diameter_mm FROM lots WHERE lot_id = ?", (lot_id,)).fetchone()
    if row is None:
        return None
    specs = json.loads(row["specs_json"] or "{}") if row["specs_json"] else {}
    ai = json.loads(row["ai_json"] or "{}") if "ai_json" in row.keys() and row["ai_json"] else {}
    return {
        "lot_id": row["lot_id"], "source": row["source"], "title": row["title"], "subtitle": row["subtitle"], "url": row["url"],
        "bidding_end_at": row["ended_at"], "status": "settled", "hammer_eur": row["hammer_eur"], "sold": bool(row["sold"]),
        "bids_count": row["bids_count"], "hearts": row["hearts"], "needs_review": row["needs_review"],
        "source_available": row["source_available"] not in ("__NO__", 0, False), "review_status": row["review_status"],
        "condition_tag": row["condition_tag"] if "condition_tag" in row.keys() else None,
        "quality": extract_quality(specs, ai),
        "movement": normalize_movement(row["movement"] if "movement" in row.keys() else None, specs),
        "case_material": normalize_material(row["case_material"] if "case_material" in row.keys() else None, specs),
        "case_diameter_mm": row["case_diameter_mm"] if "case_diameter_mm" in row.keys() else None,
        "unclassified_reason": specs.get("unclassified_reason"),
        "highest_bid_eur": specs.get("highest_bid_eur"),
        "cover": cover_metadata(fetch_lot_image(conn, row["lot_id"]))
    }
