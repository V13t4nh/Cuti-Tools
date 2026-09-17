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

def list_auctions(conn, settings, params, pagination_fn, freshness_json_fn, freshness):
    query, wanted = params.get("q", [""])[0].strip().lower(), params.get("status", ["all"])[0].strip().lower()
    today = date.today().isoformat()
    conditions_raw = params.get("conditions", [""])[0].strip().lower()
    qualities_raw = params.get("qualities", [""])[0].strip().lower()
    where, args = [], []
    if query:
        where.append("(instr(lower(coalesce(lot_id, '')), ?) > 0 OR instr(lower(coalesce(title, '')), ?) > 0 OR instr(lower(coalesce(subtitle, '')), ?) > 0)")
        args.extend([query] * 3)
    if wanted == "settled":
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
        clause = f" WHERE {' AND '.join(where)}" if where else ""
        total = conn.execute(f"SELECT COUNT(*) FROM lots{clause}", args).fetchone()[0]
        offset, pagination = pagination_fn(params, total)
        rows = conn.execute(f"SELECT lot_id, source, title, subtitle, url, ended_at, hammer_eur, sold, bids_count, hearts, needs_review, source_available, review_status, specs_json, condition_tag, ai_json FROM lots{clause} ORDER BY ended_at DESC, lot_id LIMIT ? OFFSET ?", [*args, pagination["page_size"], offset]).fetchall()
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
                "unclassified_reason": s_obj.get("unclassified_reason"),
                "highest_bid_eur": s_obj.get("highest_bid_eur"),
                "cover": cover_metadata(fetch_lot_image(conn, r["lot_id"]))
            })
        return {"state": "loaded", "data_freshness": freshness_json_fn(freshness), "lots": lots, "pagination": pagination}
    state_sql = "bidding_end_at IS NOT NULL AND bidding_end_at <> '' AND bidding_end_at > ?"
    if wanted == "open": where.append(state_sql); args.append(today)
    elif wanted == "waiting": where.append(f"NOT ({state_sql})"); args.append(today)
    elif wanted != "all": where.append("0")
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM live_watch{clause}", args).fetchone()[0]
    offset, pagination = pagination_fn(params, total)
    rows = conn.execute(f"SELECT lot_id, source, title, subtitle, url, bidding_end_at FROM live_watch{clause} ORDER BY bidding_end_at, lot_id LIMIT ? OFFSET ?", [*args, pagination["page_size"], offset]).fetchall()
    lots = [{"lot_id": r["lot_id"], "source": r["source"], "title": r["title"], "subtitle": r["subtitle"], "url": r["url"], "bidding_end_at": r["bidding_end_at"], "status": "open" if r["bidding_end_at"] and r["bidding_end_at"] > today else "waiting", "condition_tag": None, "quality": None, "cover": cover_metadata(fetch_lot_image(conn, r["lot_id"]))} for r in rows]
    return {"state": "loaded", "data_freshness": freshness_json_fn(freshness), "lots": lots, "pagination": pagination}

def get_auction_lot(conn, lot_id: str) -> dict[str, object] | None:
    row = conn.execute("SELECT lot_id, source, title, subtitle, url, bidding_end_at FROM live_watch WHERE lot_id = ?", (lot_id,)).fetchone()
    if row is not None:
        end = row["bidding_end_at"]
        status = "open" if end and end > date.today().isoformat() else "waiting"
        return {"lot_id": row["lot_id"], "source": row["source"], "title": row["title"], "subtitle": row["subtitle"], "url": row["url"], "bidding_end_at": end, "status": status, "condition_tag": None, "quality": None, "cover": cover_metadata(fetch_lot_image(conn, row["lot_id"]))}
    row = conn.execute("SELECT lot_id, source, title, subtitle, url, ended_at, hammer_eur, sold, bids_count, hearts, needs_review, source_available, review_status, specs_json, condition_tag, ai_json FROM lots WHERE lot_id = ?", (lot_id,)).fetchone()
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
        "unclassified_reason": specs.get("unclassified_reason"),
        "highest_bid_eur": specs.get("highest_bid_eur"),
        "cover": cover_metadata(fetch_lot_image(conn, row["lot_id"]))
    }
