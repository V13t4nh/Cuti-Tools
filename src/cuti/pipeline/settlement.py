"""Internal two-phase settlement state machine shared by report commands."""
from __future__ import annotations
import sqlite3
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Mapping
from ..config import Settings
from ..errors import FetchError, NormalizationError, ScrapeError
from ..models import Condition, Lot, WatchForm
from ..normalize import Rules, classify
from ..scrapers.catawiki_lot_page import parse_lot_page
from .settlement_resolver import resolve_typed_fields
from .gallery import extract_lot_gallery
from ..scrapers import catawiki_api
from ..storage import (LiveWatchRow, delete_live_watch, upsert_live_watch,
                       upsert_lot_gallery_images, upsert_lots)
@dataclass(slots=True)
class _Settlement:
    lots: list[Lot]; finished: list[str]; refreshed: list[LiveWatchRow]
    sold: int = 0; unsold: int = 0; still_open: int = 0; vanished: int = 0
    unclassified: int = 0; details_failed: int = 0
    galleries: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
def _condition_from_specs(details: object) -> Condition | None:
    if details is None:
        return None
    specs = getattr(details, "specs", None) or getattr(details, "details", None)
    if not isinstance(specs, dict) and isinstance(details, dict):
        specs = details.get("specs") or details.get("details") or details
    if not isinstance(specs, dict):
        return None
    box = specs.get("Original box included") or specs.get("Box included") or specs.get("Original box") or specs.get("Box")
    papers = specs.get("Original papers included") or specs.get("Papers included") or specs.get("Original papers") or specs.get("Papers") or specs.get("Original warranty included")
    b = (box.strip().lower() in ("yes", "co", "true", "1")) if box else (False if box and box.strip().lower() in ("no", "khong", "false", "0") else None)
    p = (papers.strip().lower() in ("yes", "co", "true", "1")) if papers else (False if papers and papers.strip().lower() in ("no", "khong", "false", "0") else None)
    if b is True and p is True:
        return Condition.FULLSET
    if b is True and p is False:
        return Condition.BOX
    if b is False and p is True:
        return Condition.PAPERS
    if b is False and p is False:
        return Condition.NAKED
    return None
def _condition_from_refinement(ai_json: object) -> Condition | None:
    accessories = ai_json.get("accessories") if isinstance(ai_json, dict) else None
    tag = accessories.get("true_condition_tag") if isinstance(accessories, dict) else None
    try:
        return Condition(tag.strip().lower()) if isinstance(tag, str) else None
    except ValueError:
        return None
def _unclassified_lot(
    row: LiveWatchRow, state: catawiki_api.LiveState, outcome: catawiki_api.BiddingOutcome,
    rules: Rules, reason: str, details: object = None, *, source_available: bool = True, review_status: str = "pending",
) -> Lot:
    brand = None
    try:
        from ..normalize import detect_brand
        brand = detect_brand(row.title, rules)
    except NormalizationError: pass
    if brand is None and details is not None: brand = getattr(details, "brand", None)
    brand_val = brand or "unknown"
    specs: dict[str, object] = {"unclassified_reason": reason}
    highest = outcome.hammer_eur or state.current_bid_eur
    if highest is not None: specs["highest_bid_eur"] = highest
    if details is not None:
        detail_specs = getattr(details, "specs", None) or getattr(details, "details", None)
        if isinstance(detail_specs, dict): specs["details"] = dict(detail_specs)
    sold = outcome.is_sold if source_available else False
    return Lot(
        lot_id=row.lot_id, source=row.source, title=row.title, brand=brand_val,
        model_key=f"{brand_val}:unclassified", condition_tag=Condition.NAKED, form=WatchForm.UNKNOWN,
        hearts=state.favorite_count, sold=sold, hammer_eur=outcome.hammer_eur if sold else None,
        opened_at=state.opened_at, ended_at=state.ended_at, url=row.url, subtitle=row.subtitle,
        bids_count=outcome.bids_count, source_available=source_available,
        needs_review=0 if review_status == "ignored" else 1, review_status=review_status,
        specs_json=json.dumps(specs, sort_keys=True),
        description=getattr(details, "description", None) if details is not None else None,
    )
def _settled_lot(
    row: LiveWatchRow,
    state: catawiki_api.LiveState,
    outcome: catawiki_api.BiddingOutcome,
    rules: Rules,
    details: object = None,
    description: str | None = None,
    override_json: object = None,
    ai_json: object = None,
) -> Lot:
    classification = classify(row.title, rules)
    condition = _condition_from_refinement(ai_json) or classification.condition or _condition_from_specs(details)
    if condition is None:
        raise NormalizationError(f"{row.lot_id}: title states no condition")
    row_details = details
    row_description = description
    resolved = resolve_typed_fields(
        row.title,
        rules,
        details=row_details,
        description=row_description,
        override_json=override_json,
        ai_json=ai_json,
    )
    if resolved.brand is None:
        raise NormalizationError(f"{row.lot_id}: no resolved brand")
    specs = dict(resolved.specs or {})
    if not outcome.is_sold:
        highest = outcome.hammer_eur or state.current_bid_eur
        if highest is not None:
            specs["highest_bid_eur"] = highest
    return Lot(
        lot_id=row.lot_id, source=row.source, title=row.title, brand=resolved.brand,
        model_key=resolved.model_key, condition_tag=condition, form=WatchForm.UNKNOWN,
        hearts=state.favorite_count, sold=outcome.is_sold, hammer_eur=outcome.hammer_eur,
        opened_at=state.opened_at, ended_at=state.ended_at, url=row.url, subtitle=row.subtitle,
        bids_count=outcome.bids_count, model=resolved.model, ref_number=resolved.ref_number,
        caliber=resolved.caliber, case_code=resolved.case_code, movement=resolved.movement,
        case_material=resolved.case_material, case_diameter_mm=resolved.case_diameter_mm,
        specs_json=json.dumps(specs, sort_keys=True), ai_json=ai_json, needs_review=resolved.needs_review,
        review_status="pending", reviewed_at=None, description=row_description,
        override_json=json.dumps(override_json, sort_keys=True) if isinstance(override_json, (dict, list)) else override_json,
    )
def settle(
    client: catawiki_api.CatawikiApi,
    rules: Rules,
    settings: Settings,
    candidates: list[LiveWatchRow],
    *,
    fetch_details: Callable[[str], str | None] | None = None,
    source_details: Mapping[str, object] | None = None,
    source_refinements: Mapping[str, object] | None = None,
    record_unclassified: bool = False,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> _Settlement:
    """Read final state for every candidate without writing anything."""
    by_id = {row.lot_id: row for row in candidates}
    result = _Settlement(lots=[], finished=[], refreshed=[])
    total_candidates = len(candidates)
    current_idx = 0
    for batch in catawiki_api.chunks(list(by_id), settings.catawiki_batch_size):
        states = client.live_states(batch)
        for lot_id in batch:
            current_idx += 1
            if on_progress is not None:
                on_progress(current_idx, total_candidates, lot_id)
            row = by_id[lot_id]

            state = states.get(lot_id)
            if state is None:
                result.vanished += 1
                result.finished.append(lot_id)
                continue
            if not state.closed:
                result.still_open += 1
                result.refreshed.append(
                    LiveWatchRow(
                        lot_id=row.lot_id, source=row.source, title=row.title,
                        subtitle=row.subtitle, url=row.url, bidding_end_at=state.ended_at,
                    )
                )
                continue
            outcome = client.outcome(lot_id)
            if not outcome.is_closed:
                result.still_open += 1
                continue
            if settings.settle_min_hearts > 0 and state.favorite_count < settings.settle_min_hearts:
                result.finished.append(lot_id)
                continue
            try:
                cached = source_details.get(lot_id) if source_details is not None else None
                ai_json = source_refinements.get(lot_id) if source_refinements is not None else None
                if cached is not None:
                    raw_specs = getattr(cached, "specs", None)
                    description = getattr(cached, "description", None)
                    if not isinstance(raw_specs, dict) or not isinstance(description, (str, type(None))):
                        raise ScrapeError(f"{lot_id}: invalid stored source details")
                    page = {"details": raw_specs}
                elif fetch_details is not None:
                    html = fetch_details(lot_id)
                    if html is None:
                        raise FetchError(f"{lot_id}: details fetch returned no document")
                    page = parse_lot_page(html, rules=rules)
                    description = page.description
                    try:
                        urls = extract_lot_gallery(html)
                        if urls:
                            result.galleries[lot_id] = urls
                    except Exception:
                        pass
                else:
                    page = None
                    description = None
                lot = _settled_lot(
                    row, state, outcome, rules, details=page,
                    description=description, ai_json=ai_json,
                )
            except (FetchError, ScrapeError) as exc:
                result.details_failed += 1
                if "404" in str(exc):
                    result.finished.append(lot_id)
                    result.lots.append(_unclassified_lot(
                        row, state, outcome, rules, f"lot_removed_by_source ({exc})",
                        source_available=False, review_status="ignored",
                    ))
                    continue
                result.errors.append(f"{lot_id}: {exc}")
                continue
            except NormalizationError as exc:
                result.unclassified += 1
                result.finished.append(lot_id)
                if record_unclassified:
                    result.lots.append(_unclassified_lot(row, state, outcome, rules, str(exc), page))
                continue
            result.lots.append(lot); result.finished.append(lot_id)
            if outcome.is_sold: result.sold += 1
            else: result.unsold += 1
    return result
def persist(conn: sqlite3.Connection, settlement: _Settlement, now: datetime) -> int:
    written = upsert_lots(conn, settlement.lots, now)
    if settlement.refreshed: upsert_live_watch(conn, settlement.refreshed, now)
    for lot_id, urls in settlement.galleries.items():
        try: upsert_lot_gallery_images(conn, lot_id, urls)
        except Exception as exc: settlement.errors.append(f"{lot_id}: gallery persistence failed: {exc}")
    delete_live_watch(conn, settlement.finished)
    return written
