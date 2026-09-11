"""Telegram cover transport and the durable one-cover worker."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Callable

from .config import Settings
from .errors import MediaUploadError
from .storage.media import (claim_lot_image, fetch_lot_images, mark_lot_image_failed,
                            mark_lot_image_ready, upsert_lot_image)


def require_telegram_credentials(settings: Settings) -> tuple[str, str]:
    """Validate bot and destination before the upload worker touches the queue."""
    token = settings.telegram_bot_token.strip()
    chat_id = (settings.telegram_channel_id or settings.telegram_chat_id).strip()
    if not token or not chat_id:
        raise MediaUploadError("Telegram credentials are not configured")
    return token, chat_id


def _parse_retry_after(exc: urllib.error.HTTPError, body: bytes | None = None) -> float | None:
    """Extract retry_after seconds from HTTP 429 Retry-After header or JSON body."""
    if exc.code != 429:
        return None
    if exc.headers and (raw := exc.headers.get("Retry-After")):
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
    try:
        raw_body = body if body is not None else exc.read()
        payload = json.loads(raw_body.decode("utf-8") if isinstance(raw_body, bytes) else raw_body)
        if isinstance(payload, dict) and (params := payload.get("parameters")):
            return float(params["retry_after"])
    except Exception:
        pass
    return None


def upload_image_to_telegram(image_source: str, caption: str, settings: Settings) -> dict[str, Any]:
    """Ask Telegram to fetch a public image URL; never download the source locally."""
    token, chat_id = require_telegram_credentials(settings)
    if not isinstance(image_source, str) or not image_source.startswith(("http://", "https://")):
        raise MediaUploadError("image source must be an HTTP(S) URL")
    api_url = f"{settings.telegram_api_base}/bot{token}/sendPhoto"

    def _post(url: str) -> dict[str, Any]:
        payload = json.dumps({"chat_id": chat_id, "photo": url, "caption": caption[:1024]}).encode("utf-8")
        req = urllib.request.Request(api_url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "Cuti/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=settings.http_timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body, desc = b"", ""
            try:
                body = exc.read()
                desc = json.loads(body.decode("utf-8")).get("description", "")
            except Exception:
                pass
            detail = f": {desc}" if desc else ""
            raise MediaUploadError(f"Telegram sendPhoto returned HTTP {exc.code}{detail}", retry_after=_parse_retry_after(exc, body)) from None
        except (urllib.error.URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise MediaUploadError("Telegram sendPhoto request failed") from None

    try:
        response = _post(image_source)
    except MediaUploadError as exc:
        err_msg = str(exc).lower()
        if "failed to get http url content" in err_msg or ("http 400" in err_msg and "cb=" not in image_source):
            sep = "&" if "?" in image_source else "?"
            response = _post(f"{image_source}{sep}cb={int(time.time())}")
        else:
            raise

    if not isinstance(response, dict) or not response.get("ok"):
        description = response.get("description") if isinstance(response, dict) else None
        detail = f": {description}" if isinstance(description, str) and description else ""
        raise MediaUploadError(f"Telegram rejected sendPhoto{detail}")
    try:
        result, photo = response["result"], response["result"]["photo"][-1]
        return {"file_id": photo["file_id"], "file_unique_id": photo.get("file_unique_id"),
                "file_path": None, "message_id": result["message_id"]}
    except (KeyError, IndexError, TypeError):
        raise MediaUploadError("Telegram sendPhoto response was missing photo metadata") from None


def telegram_get_file(settings: Settings, file_id: str) -> str:
    """Resolve a Telegram file id to its path without returning a tokenized URL."""
    token, _ = require_telegram_credentials(settings)
    query = urllib.parse.urlencode({"file_id": file_id})
    request = urllib.request.Request(f"{settings.telegram_api_base}/bot{token}/getFile?{query}", headers={"User-Agent": "Cuti/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=settings.http_timeout_seconds) as resp:
            response = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise MediaUploadError("Telegram getFile request failed") from None
    try:
        path = response["result"]["file_path"]
    except (KeyError, TypeError):
        raise MediaUploadError("Telegram getFile response was missing file metadata") from None
    if not response.get("ok") or not isinstance(path, str) or not path:
        raise MediaUploadError("Telegram getFile was rejected")
    return path


def queue_lot_images(conn: sqlite3.Connection, lot_id: str, image_urls: list[str]) -> list[dict[str, Any]]:
    """Persist at most one immutable cover URL for the separate upload worker."""
    if len(image_urls) > 1:
        raise MediaUploadError("one-cover flow accepts at most one image URL")
    with conn:
        for idx, url in enumerate(image_urls):
            upsert_lot_image(conn, lot_id=lot_id, idx=idx, source_url=url)
    return fetch_lot_images(conn, lot_id)


def upload_lot_images(conn: sqlite3.Connection, lot_id: str, title: str, image_urls: list[str], settings: Settings) -> list[dict[str, Any]]:
    """Backward-compatible name for queueing; Telegram work is worker-only."""
    del title, settings
    return queue_lot_images(conn, lot_id, image_urls)


def _retryable(error: MediaUploadError) -> bool:
    text = str(error).lower()
    if "request failed" in text or "timeout" in text or "429" in text or "failed to get http url content" in text:
        return True
    marker = "http "
    if marker in text:
        try:
            code = int(text.split(marker, 1)[1].split()[0].rstrip(":,"))
            return code == 429 or code >= 500
        except (IndexError, ValueError):
            return False
    return "retry" in text


def process_lot_image_queue(conn: sqlite3.Connection, settings: Settings, now: datetime, *, limit: int = 20,
                            worker_id: str | None = None, sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Claim, upload and finalize covers with bounded retries and leases."""
    if limit < 1:
        raise MediaUploadError("upload-images limit must be a positive integer")
    require_telegram_credentials(settings)
    worker = worker_id or f"cuti-media-{os.getpid()}"
    uploaded, failed = 0, []
    for number in range(limit):
        row = claim_lot_image(conn, worker_id=worker, now=now, lease_seconds=settings.telegram_upload_lease_seconds)
        if row is None:
            break
        if number and settings.telegram_upload_pause_seconds:
            sleep(settings.telegram_upload_pause_seconds)
        title_row = conn.execute("SELECT title FROM lots WHERE lot_id = ?", (row["lot_id"],)).fetchone()
        if title_row is None:
            title_row = conn.execute("SELECT title FROM live_watch WHERE lot_id = ?", (row["lot_id"],)).fetchone()
        title = title_row[0] if title_row else ""
        caption = f"Lot {row['lot_id']} | {title} (#1)"
        try:
            result = upload_image_to_telegram(row["source_url"], caption, settings)
            mark_lot_image_ready(conn, lot_id=row["lot_id"], idx=row["idx"], worker_id=worker,
                                 file_id=result["file_id"], file_path=result.get("file_path"),
                                 message_id=result.get("message_id"), uploaded_at=now)
            uploaded += 1
        except MediaUploadError as exc:
            retry_after = getattr(exc, "retry_after", None)
            state = mark_lot_image_failed(conn, lot_id=row["lot_id"], idx=row["idx"], worker_id=worker,
                                          error=str(exc), now=now, retryable=_retryable(exc),
                                          max_attempts=settings.telegram_upload_max_attempts,
                                          base_pause_seconds=settings.telegram_upload_pause_seconds,
                                          max_backoff_seconds=settings.telegram_upload_max_backoff_seconds,
                                          retry_after=retry_after)
            failed.append({"lot_id": row["lot_id"], "idx": row["idx"], "state": state, "error": str(exc)})
            if retry_after is not None and retry_after > 0:
                sleep(retry_after + 1.0)
    return {"candidates": uploaded + len(failed), "uploaded": uploaded, "failed": failed}



def cover_metadata(image: dict[str, Any] | None) -> dict[str, Any]:
    """Return typed public cover state; ready media uses the same-origin route."""
    if image is None:
        return {"state": "missing", "url": None, "source_url": None, "attempts": 0,
                "last_error": None, "next_attempt_at": None}
    state = image.get("state") or ("ready" if image.get("telegram_file_id") else "queued")
    ready = state == "ready"
    public_url = f"/api/media/lots/{urllib.parse.quote(str(image['lot_id']), safe='')}/cover" if ready else None
    return {"state": state, "url": public_url,
            "source_url": image["source_url"] if state in {"queued", "uploading"} else None,
            "attempts": image.get("attempts", 0), "last_error": image.get("last_error"),
            "next_attempt_at": image.get("next_attempt_at")}


def format_lot_images(images: list[dict[str, Any]], _settings: Settings) -> list[dict[str, Any]]:
    """Format images: idx=0 uses same-origin cover route, idx>=1 uses direct CDN URLs when ready."""
    formatted = []
    for img in images:
        idx = img.get("idx", 0)
        meta = cover_metadata(img)
        item = {
            **meta,
            "lot_id": img["lot_id"],
            "idx": idx,
            "telegram_file_id": img.get("telegram_file_id"),
            "telegram_file_path": img.get("telegram_file_path"),
            "uploaded_at": img.get("uploaded_at"),
            "direct_url": meta["url"],
        }
        if idx > 0 and meta["state"] == "ready" and not img.get("telegram_file_id"):
            src_url = img.get("source_url")
            item["url"] = src_url
            item["direct_url"] = src_url
            item["source_url"] = src_url
        formatted.append(item)
    return formatted
