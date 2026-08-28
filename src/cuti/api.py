from __future__ import annotations
import math; from datetime import date, datetime, timezone
from urllib.parse import parse_qs, unquote; from .comparables import find_comparables; from .config import Settings
from .errors import CutiError, PricingError, StorageError; from .evaluation import cost_to_eur
from .evaluation_chart import evaluate_deal_with_chart; from .liquidity import compute_liquidity; from .models import Condition; from .normalize import load_rules
from .config_pricing_store import profile_from_payload; from .storage import (CanonicalProduct, DataFreshness, assess_data_freshness, count_lot_images, create_tracked_deal, fetch_lot_image, fetch_product, fetch_tracked_deal, list_saved_products, list_tracked_deals, save_product, search_products, unsave_product, update_deal_status)
class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: object | None = None) -> None:
        super().__init__(message); self.status, self.code, self.message, self.details = status, code, message, details
def _product(product: CanonicalProduct) -> dict[str, object]:
    return {"product_id": product.product_id, "canonical_name": product.canonical_name, "brand": product.brand, "reference": product.reference, "model_key": product.model_key, "aliases": list(product.aliases), "provenance": product.provenance}
def _freshness(conn, settings: Settings) -> DataFreshness:
    return assess_data_freshness(conn, now=datetime.now(timezone.utc),
                                 stale_after_hours=settings.data_stale_after_hours)
def _freshness_json(value: DataFreshness) -> dict[str, object]:
    return {"status": value.status, "last_updated_at": value.last_updated_at,
            "age_hours": round(value.age_hours, 2) if value.age_hours is not None else None,
            "stale_after_hours": value.stale_after_hours}
def _require_body(body: object) -> dict[str, object]:
    if not isinstance(body, dict):
        raise ApiError(400, "invalid_body", "Request body must be an object")
    return body
def _required_string(body: dict[str, object], name: str) -> str:
    value = body.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, "missing_field", f"{name} is required", {"field": name})
    return value.strip()
def _image_urls(body: dict[str, object]) -> list[str]:
    values = body.get("image_urls")
    if not isinstance(values, list): raise ApiError(400, "missing_field", "image_urls must be a list", {"field": "image_urls"})
    urls = [value.strip() for value in values if isinstance(value, str) and value.strip().startswith(("http://", "https://"))]
    if len(urls) != len(values): raise ApiError(400, "invalid_image_url", "image_urls must contain HTTP(S) URLs")
    if len(urls) != 1: raise ApiError(400, "invalid_cover_count", "Exactly one cover image URL is required")
    return urls
def _amount(body: dict[str, object]) -> float:
    value = body.get("ask_price")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value <= 0:
        raise ApiError(400, "invalid_amount", "ask_price must be a finite number greater than zero", {"field": "ask_price"})
    return float(value)
def _pagination(params: dict[str, list[str]], total: int) -> tuple[int, dict[str, int]]:
    values = []
    for name, default, maximum in (("page", 1, None), ("page_size", 8, 100)):
        raw = (params.get(name) or [str(default)])[0]
        try: value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ApiError(400, "invalid_pagination", f"{name} must be an integer", {"field": name}) from exc
        if value < 1 or maximum and value > maximum: raise ApiError(400, "invalid_pagination", f"{name} must be in range 1..{maximum or 'infinity'}", {"field": name})
        values.append(value)
    page, page_size = values; total_pages = math.ceil(total / page_size) if total else 0
    page = min(page, total_pages) if total_pages else 1
    return (page - 1) * page_size, {"page": page, "page_size": page_size, "total": total, "total_pages": total_pages}
def _status_payload(conn, settings: Settings, freshness: DataFreshness) -> dict[str, object]:
    count = lambda table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    source_state = "no_data" if freshness.status == "no_data" else freshness.status
    return {"state": "loaded", "lots_count": count("lots"), "live_watch_count": count("live_watch"),
            "eur_vnd_rate": settings.pricing_profile.values["eur_vnd_rate"], "match_threshold": settings.match_threshold,
            "min_comparables": settings.min_comparables, "data_freshness": _freshness_json(freshness),
            "media": count_lot_images(conn),
            "sources": [{"name": "catawiki", "status": source_state,
                          "last_updated_at": freshness.last_updated_at}],
            "coverage": {"lots": count("lots"), "live_lots": count("live_watch")}}
def _liquidity_row(item, *, insufficient: bool = False) -> dict[str, object]:
    return {"brand": item[0] if insufficient else item.brand, "form": item[1].value if insufficient else item.form.value,
            "data_state": "insufficient_data" if insufficient else "available",
            "lots": item[2] if insufficient else item.lots, "sold": None if insufficient else item.sold,
            "sell_through": None if insufficient else item.sell_through,
            "median_days_to_close": None if insufficient else item.median_days_to_close,
            "speed": None if insufficient else item.speed, "heart_to_hammer": None if insufficient else item.heart_to_hammer,
            "index": None if insufficient else item.index, "latest_qoq_change": None if insufficient else item.latest_qoq_change,
            "stop_buying": False if insufficient else item.stop_buying,
            "status": None if insufficient else item.status}
def _liquidity(conn, settings: Settings, params: dict[str, list[str]]) -> dict[str, object]:
    freshness = _freshness(conn, settings)
    if freshness.status == "no_data": _, pagination = _pagination(params, 0); return {"state": "no_data", "data_freshness": _freshness_json(freshness), "groups": [], "pagination": pagination}
    report = compute_liquidity(conn, settings, date.today())
    rows = [_liquidity_row(item) for item in report.brands]
    rows.extend(_liquidity_row(item, insufficient=True) for item in report.excluded_groups); [row.update({"window_start": report.window_start, "window_end": report.window_end}) for row in rows]
    brand = params.get("brand", [""])[0].strip().lower()
    status = params.get("status", ["all"])[0].strip().lower()
    if brand: rows = [row for row in rows if brand in row["brand"].lower()]
    if status != "all": rows = [row for row in rows if ("stop_buying" if row["stop_buying"] else row["status"] or "insufficient_data") == status]
    rows.sort(key=lambda row: (-(row["index"] if row["index"] is not None else -1), row["brand"], row["form"]))
    offset, pagination = _pagination(params, len(rows))
    return {"state": "loaded", "data_freshness": _freshness_json(freshness), "groups": rows[offset:offset + pagination["page_size"]], "pagination": pagination}
def _auction(conn, settings: Settings, params: dict[str, list[str]]) -> dict[str, object]:
    freshness = _freshness(conn, settings)
    query = params.get("q", [""])[0].strip().lower()
    wanted = params.get("status", ["all"])[0].strip().lower()
    today = date.today().isoformat()
    where, args = [], []
    if query:
        where.append("(instr(lower(coalesce(lot_id, '')), ?) > 0 OR instr(lower(coalesce(title, '')), ?) > 0 OR instr(lower(coalesce(subtitle, '')), ?) > 0)")
        needle = query; args.extend([needle] * 3)
    state_sql = "bidding_end_at IS NOT NULL AND bidding_end_at <> '' AND bidding_end_at > ?"
    if wanted == "open":
        where.append(state_sql); args.append(today)
    elif wanted == "waiting":
        where.append(f"NOT ({state_sql})"); args.append(today)
    elif wanted != "all":
        where.append("0")
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM live_watch{clause}", args).fetchone()[0]
    offset, pagination = _pagination(params, total)
    rows = conn.execute(f"SELECT lot_id, source, title, subtitle, url, bidding_end_at FROM live_watch{clause} ORDER BY bidding_end_at, lot_id LIMIT ? OFFSET ?", [*args, pagination["page_size"], offset]).fetchall()
    lots = []
    for row in rows:
        end = row["bidding_end_at"]; state = "open" if end and end > today else "waiting"
        from .telegram_media import cover_metadata
        lots.append({"lot_id": row["lot_id"], "source": row["source"], "title": row["title"], "subtitle": row["subtitle"], "url": row["url"], "bidding_end_at": end, "status": state, "cover": cover_metadata(fetch_lot_image(conn, row["lot_id"]))})
    return {"state": "loaded", "data_freshness": _freshness_json(freshness), "lots": lots, "pagination": pagination}
def get(conn, settings: Settings, path: str, params: dict[str, list[str]]) -> tuple[int, dict[str, object]]:
    parts = [unquote(part) for part in path.strip("/").split("/") if part]
    if parts == ["api", "pricing-config"]: from .api_pricing import get as pricing_get; return pricing_get(settings)
    if parts == ["api", "status"]:
        freshness = _freshness(conn, settings)
        return 200, _status_payload(conn, settings, freshness)
    if parts == ["api", "products", "search"]:
        query = params.get("q", [""])[0]
        return 200, {"state": "initial" if not query.strip() else "loaded", "products": [_product(item) for item in search_products(conn, query)]}
    if len(parts) == 3 and parts[:2] == ["api", "products"]:
        product = fetch_product(conn, parts[2])
        if product is None: raise ApiError(404, "not_found", "Product was not found")
        return 200, {"state": "loaded", "product": _product(product)}
    if parts == ["api", "saved-products"]:
        return 200, {"state": "loaded", "products": [_product(item) for item in list_saved_products(conn)]}
    if len(parts) == 3 and parts[:2] == ["api", "saved-products"]:
        product = fetch_product(conn, parts[2])
        if product is None: raise ApiError(404, "not_found", "Saved product was not found")
        return 200, {"state": "loaded", "product": _product(product), "data_freshness": _freshness_json(_freshness(conn, settings))}
    if parts == ["api", "deals"]:
        query = params.get("q", [""])[0]
        return 200, {"state": "loaded", "deals": [_deal(item) for item in list_tracked_deals(conn, query)]}
    if len(parts) == 3 and parts[:2] == ["api", "deals"]:
        try: deal_id = int(parts[2])
        except ValueError as exc: raise ApiError(400, "invalid_id", "Deal id must be an integer") from exc
        deal = fetch_tracked_deal(conn, deal_id)
        if deal is None: raise ApiError(404, "not_found", "Deal was not found")
        return 200, {"state": "loaded", "deal": _deal(deal), "data_freshness": _freshness_json(_freshness(conn, settings))}
    if parts == ["api", "liquidity"]:
        return 200, _liquidity(conn, settings, params)
    if len(parts) == 4 and parts[:2] == ["api", "liquidity"]:
        payload = _liquidity(conn, settings, {"brand": [parts[2]]}); rows = [row for row in payload["groups"] if row["form"] == parts[3]]
        if not rows: raise ApiError(404, "not_found", "Liquidity segment was not found")
        return 200, {"state": payload["state"], "segment": rows[0], "data_freshness": payload["data_freshness"]}
    if parts == ["api", "auction-lots"]:
        return 200, _auction(conn, settings, params)
    if len(parts) == 3 and parts[:2] == ["api", "auction-lots"]:
        row = conn.execute("SELECT lot_id, source, title, subtitle, url, bidding_end_at FROM live_watch WHERE lot_id = ?", (parts[2],)).fetchone()
        if row is None: raise ApiError(404, "not_found", "Auction lot was not found")
        from .telegram_media import cover_metadata
        end = row["bidding_end_at"]; status = "open" if end and end > date.today().isoformat() else "waiting"
        return 200, {"state": "loaded", "lot": {"lot_id": row["lot_id"], "source": row["source"], "title": row["title"], "subtitle": row["subtitle"], "url": row["url"], "bidding_end_at": end, "status": status, "cover": cover_metadata(fetch_lot_image(conn, row["lot_id"]))}}
    if len(parts) == 4 and parts[:2] == ["api", "lots"] and parts[3] == "images":
        from .telegram_media import fetch_lot_images, format_lot_images
        return 200, {"state": "loaded", "lot_id": parts[2], "images": format_lot_images(fetch_lot_images(conn, parts[2]), settings)}
    raise ApiError(404, "not_found", f"Endpoint not found: {path}")
def _deal(deal) -> dict[str, object]:
    return {"id": deal.id, "product": _product(deal.product), "ask_price": deal.ask_amount,
            "currency": deal.currency, "condition": deal.condition.value, "status": deal.status,
            "snapshot": deal.snapshot, "created_at": deal.created_at, "updated_at": deal.updated_at}
def write(conn, settings: Settings, method: str, path: str, body: object) -> tuple[int, dict[str, object]]:
    parts = [unquote(part) for part in path.strip("/").split("/") if part]; payload = _require_body(body)
    if (parts == ["api", "pricing-config"] and method == "PUT") or (parts == ["api", "pricing-config", "preview"] and method == "POST"): from .api_pricing import write as pricing_write; return pricing_write(settings, method, payload)
    if method == "POST" and parts == ["api", "evaluate"]:
        product_id = _required_string(payload, "product_id"); product = fetch_product(conn, product_id)
        if product is None: raise ApiError(404, "unknown_product", "Choose a product from the search results first")
        amount = _amount(payload); currency, condition_text = _required_string(payload, "currency").lower(), _required_string(payload, "condition").lower()
        if currency not in {"vnd", "eur"}: raise ApiError(400, "invalid_currency", "currency must be vnd or eur", {"field": "currency"})
        try: condition = Condition.parse(condition_text)
        except CutiError as exc: raise ApiError(400, "invalid_condition", str(exc), {"field": "condition"}) from exc
        freshness = _freshness(conn, settings)
        if freshness.status == "no_data": raise ApiError(409, "no_data", "Chưa có dữ liệu thị trường để thẩm định")
        rules, query = load_rules(settings.rules_path), f"{product.canonical_name} {product.reference}"
        try:
            result = evaluate_deal_with_chart(conn, rules, settings, query=query, cost=amount, currency=currency, condition=condition, today=date.today())
        except (CutiError, ValueError, PricingError) as exc: raise ApiError(422, "evaluation_error", str(exc)) from exc
        decision, chart = result.decision, result.chart; comparables = find_comparables(conn, title=query, condition=condition, rules=rules, settings=settings, today=date.today())
        ask_vnd = int(round(amount if currency == "vnd" else cost_to_eur(amount, "eur", settings) * settings.pricing_profile.values["eur_vnd_rate"])); max_buy = decision.max_buy_cost_vnd
        return 200, {"state": "insufficient_data" if decision.verdict.value == "insufficient_data" else "loaded",
            "product": _product(product), "input": {"ask_price": amount, "currency": currency, "condition": condition.value},
            "data_freshness": _freshness_json(freshness), "decision": {"verdict": decision.verdict.value,
            "max_buy_price_vnd": max_buy, "price_gap_vnd": max_buy - ask_vnd if max_buy is not None else None,
            "sample_size": decision.sample_size, "attempt_count": decision.attempt_count,
            "sell_through_rate": decision.sell_through_rate, "median_days_to_close": decision.median_days_to_close,
            "heart_to_hammer_rate": decision.heart_to_hammer_rate, "net_p25_eur": decision.net_p25_eur,
            "net_median_eur": decision.net_median_eur, "net_p75_eur": decision.net_p75_eur,
            "reason": decision.reason, "threshold_eur": decision.threshold_eur},
            "evidence": [{"lot_id": item.lot.lot_id, "title": item.lot.title, "hammer_eur": item.lot.hammer_eur,
                          "ended_at": item.lot.ended_at, "score": round(item.score, 3), "url": item.lot.url} for item in comparables],
            "chart": {"hammer_prices_eur": list(chart.hammer_prices_eur), "input_hammer_eur": chart.input_hammer_eur,
                      "cycle_position": chart.cycle_position, "heart_acceleration_rate": chart.heart_acceleration_rate}, "pricing_profile": settings.pricing_profile.public()}
    if method == "POST" and parts == ["api", "saved-products"]:
        product_id = _required_string(payload, "product_id")
        if fetch_product(conn, product_id) is None: raise ApiError(404, "unknown_product", "Product was not found")
        created = save_product(conn, product_id, datetime.now(timezone.utc)); return 201 if created else 200, {"state": "saved", "created": created, "product_id": product_id}
    if method == "DELETE" and len(parts) == 3 and parts[:2] == ["api", "saved-products"]:
        return 200, {"state": "unsaved", "removed": unsave_product(conn, parts[2]), "product_id": parts[2]}
    if method == "POST" and parts == ["api", "deals"]:
        product_id = _required_string(payload, "product_id")
        if fetch_product(conn, product_id) is None: raise ApiError(404, "unknown_product", "Product was not found")
        amount, currency, condition_text = _amount(payload), _required_string(payload, "currency").lower(), _required_string(payload, "condition").lower()
        if currency not in {"vnd", "eur"}: raise ApiError(400, "invalid_currency", "currency must be vnd or eur")
        try: condition = Condition.parse(condition_text)
        except CutiError as exc: raise ApiError(400, "invalid_condition", str(exc)) from exc
        snapshot = payload.get("snapshot")
        if not isinstance(snapshot, dict): raise ApiError(400, "missing_field", "snapshot is required", {"field": "snapshot"})
        profile_payload = snapshot.get("pricing_profile")
        if not isinstance(profile_payload, dict): raise ApiError(400, "missing_field", "snapshot.pricing_profile is required", {"field": "snapshot.pricing_profile"})
        try: historical_profile = profile_from_payload(profile_payload)
        except CutiError as exc: raise ApiError(422, "invalid_pricing_profile", str(exc), {"field": "snapshot.pricing_profile"}) from exc
        if not isinstance(profile_payload.get("revision"), str) or profile_payload["revision"] != historical_profile.revision: raise ApiError(422, "invalid_pricing_profile_revision", "snapshot.pricing_profile revision does not match its contents", {"field": "snapshot.pricing_profile.revision"})
        deal, created = create_tracked_deal(conn, product_id=product_id, ask_amount=amount, currency=currency, condition=condition, snapshot=snapshot, now=datetime.now(timezone.utc))
        return 201 if created else 200, {"state": "saved", "created": created, "deal": _deal(deal)}
    if method == "PATCH" and len(parts) == 3 and parts[:2] == ["api", "deals"]:
        status = _required_string(payload, "status").lower()
        try: deal = update_deal_status(conn, int(parts[2]), status, datetime.now(timezone.utc))
        except (ValueError, StorageError) as exc: raise ApiError(409 if "transition" in str(exc) else 400, "invalid_status", str(exc)) from exc
        return 200, {"state": "updated", "deal": _deal(deal)}
    if method == "POST" and len(parts) == 4 and parts[:2] == ["api", "lots"] and parts[3] == "images":
        from .telegram_media import format_lot_images, queue_lot_images; urls = _image_urls(payload)
        exists = conn.execute("SELECT 1 FROM live_watch WHERE lot_id = ? UNION SELECT 1 FROM lots WHERE lot_id = ?", (parts[2], parts[2])).fetchone()
        if exists is None: raise ApiError(404, "not_found", "Lot was not found")
        try: images = queue_lot_images(conn, parts[2], urls)
        except StorageError as exc: raise ApiError(409, "image_conflict", str(exc)) from exc
        return 200, {"state": "queued", "lot_id": parts[2], "queued_count": len(urls), "images": format_lot_images(images, settings)}
    raise ApiError(404, "not_found", f"Endpoint not found: {path}")
def query_params(raw_query: str) -> dict[str, list[str]]: return parse_qs(raw_query, keep_blank_values=True)
def error_payload(error: ApiError) -> dict[str, object]:
    return {"error": {"code": error.code, "message": error.message, "details": error.details}}
