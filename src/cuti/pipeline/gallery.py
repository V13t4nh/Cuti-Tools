"""Lot gallery extraction and on-demand reconciliation helpers."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from ..config_types import Settings
from ..errors import ScrapeError
from ..fetch import fetch_text
from ..storage.gallery import upsert_lot_gallery_images
from ..storage.media import fetch_lot_images


def extract_lot_gallery(html: str) -> list[str]:
    """Extract distinct high-resolution image URLs for a lot from HTML.

    Prefers structured photo records in __NEXT_DATA__, falling back to
    regex discovery against assets.catawiki.nl with thumbnail stripping.
    """
    if not html or not isinstance(html, str):
        return []

    found: list[str] = []
    seen: set[str] = set()

    # 1. Try structured __NEXT_DATA__
    next_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if next_match:
        try:
            data = json.loads(next_match.group(1))
            props = data.get("props", {}).get("pageProps", {})
            lot_data = props.get("lotDetailsData", {})
            images_list = lot_data.get("images", [])
            if isinstance(images_list, list):
                for item in images_list:
                    if isinstance(item, dict):
                        # 'large' is the highest resolution available; fallback to 'id'
                        candidate = item.get("large") or item.get("id") or item.get("medium")
                        if isinstance(candidate, str) and candidate.startswith("http"):
                            clean_url = re.sub(r'/thumb\d*_', '/', candidate.strip())
                            if clean_url not in seen:
                                seen.add(clean_url)
                                found.append(clean_url)
        except Exception:
            pass

    if found:
        return found

    # 2. Fallback regex search (only if __NEXT_DATA__ has no images)
    raw_matches = re.findall(r'https://assets\.catawiki\.nl/assets/[^"\'\s<>]+?\.(?:jpg|jpeg|png|webp)', html, re.IGNORECASE)
    for m in raw_matches:
        # Filter out UI assets, categories, or avatars
        if any(token in m for token in ("/categories/", "/buyer/", "/buyer_ui/", "shoplive")):
            continue
        clean_url = re.sub(r'/thumb\d*_', '/', m.strip())
        if clean_url not in seen:
            seen.add(clean_url)
            found.append(clean_url)

    return found


def on_demand_fetch_lot_gallery(
    conn: sqlite3.Connection,
    lot_id: str,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Fetch a lot's HTML on demand, store gallery images, and return updated records."""
    row = conn.execute(
        "SELECT url FROM live_watch WHERE lot_id = ? UNION SELECT url FROM lots WHERE lot_id = ?",
        (lot_id, lot_id),
    ).fetchone()
    if not row or not row[0]:
        return fetch_lot_images(conn, lot_id)

    lot_url = str(row[0])
    html = fetch_text(lot_url, timeout_seconds=settings.http_timeout_seconds)
    gallery_urls = extract_lot_gallery(html)

    if gallery_urls:
        upsert_lot_gallery_images(conn, lot_id, gallery_urls)

    return fetch_lot_images(conn, lot_id)


def get_lot_gallery_images(conn: sqlite3.Connection, lot_id: str, settings: Settings) -> list[dict[str, Any]]:
    """Return formatted images, on-demand hydrating extended gallery if missing."""
    from cuti.telegram_media import format_lot_images
    images = fetch_lot_images(conn, lot_id)
    if len(images) <= 1:
        try:
            images = on_demand_fetch_lot_gallery(conn, lot_id, settings)
        except Exception:
            pass
    return format_lot_images(images, settings)

