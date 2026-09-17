"""Vercel Serverless Function entrypoint for CUTI REST API.

Provides both WSGI callable (app) and BaseHTTPRequestHandler (handler)
for 100% compatibility with Vercel's Python runtime.
"""

from __future__ import annotations

import json
import math
import os
import secrets
import sys
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Resolve project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# In Vercel serverless environment, writable directory is /tmp
TMP_DB = Path("/tmp/auctions.db")
os.environ["CUTI_DB_PATH"] = str(TMP_DB)
os.environ["CUTI_HOME"] = str(PROJECT_ROOT)
os.environ["CUTI_NOTIFIER_FILE_PATH"] = "/tmp/alerts.jsonl"
os.environ["CUTI_REPORT_PATH"] = "/tmp/report.html"

from cuti.api import ApiError, error_payload, get, query_params, write
from cuti.config import load_settings
from cuti.errors import MediaUploadError
from cuti.r2 import ensure_database_synced
from cuti.server import CutiApiHandler, _check_auth, _local_origin
from cuti.storage import connect, ensure_catalog, fetch_lot_image, load_catalog
from cuti.telegram_media import require_telegram_credentials, telegram_get_file

CORS_HEADERS = [
    ("Access-Control-Allow-Origin", "*"),
    ("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS"),
    ("Access-Control-Allow-Headers", "Content-Type, Authorization"),
]


def app(environ: dict, start_response: object) -> list[bytes]:
    """WSGI callable application for Vercel Serverless."""
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/").rstrip("/")
    query = environ.get("QUERY_STRING", "")

    # If Vercel rewrote via x-matched-path, use the original requested path
    matched = environ.get("HTTP_X_MATCHED_PATH")
    if matched and matched.startswith("/api"):
        path = matched.rstrip("/")

    # Normalize root path
    if not path:
        path = "/api/status"

    # Preflight OPTIONS
    if method == "OPTIONS":
        start_response("204 No Content", CORS_HEADERS)
        return [b""]

    # Ensure database is present in /tmp
    try:
        ensure_database_synced(TMP_DB)
    except Exception as exc:
        err_bytes = json.dumps({"error": {"code": "r2_sync_failed", "message": str(exc)}}).encode("utf-8")
        start_response("500 Internal Server Error", [("Content-Type", "application/json"), *CORS_HEADERS])
        return [err_bytes]

    # Parse headers
    headers = {
        "Authorization": environ.get("HTTP_AUTHORIZATION", ""),
        "Cookie": environ.get("HTTP_COOKIE", ""),
        "Origin": environ.get("HTTP_ORIGIN", ""),
    }

    settings = load_settings()
    is_auth = _check_auth(headers, query, settings.auth_secret)

    # Read body for write methods
    body = None
    if method in {"POST", "PUT", "PATCH"}:
        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
            if content_length > 0:
                raw_body = environ["wsgi.input"].read(content_length).decode("utf-8")
                body = json.loads(raw_body) if raw_body.strip() else {}
            else:
                body = {}
        except Exception as exc:
            err_bytes = json.dumps({"error": {"code": "invalid_json", "message": str(exc)}}).encode("utf-8")
            start_response("400 Bad Request", [("Content-Type", "application/json"), *CORS_HEADERS])
            return [err_bytes]

    # Auth routes
    if path == "/api/auth/check" and method == "GET":
        payload = json.dumps({"authenticated": is_auth, "required": bool(settings.auth_secret)}).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json"), *CORS_HEADERS])
        return [payload]

    if path == "/api/auth/login" and method == "POST":
        given = str((body if isinstance(body, dict) else {}).get("secret", ""))
        if not settings.auth_secret or secrets.compare_digest(given, settings.auth_secret):
            cookie = f"cuti_token={settings.auth_secret}; Path=/; SameSite=Lax"
            payload = json.dumps({"ok": True, "token": settings.auth_secret}).encode("utf-8")
            start_response("200 OK", [("Content-Type", "application/json"), ("Set-Cookie", cookie), *CORS_HEADERS])
        else:
            payload = json.dumps({"error": {"code": "invalid_credentials", "message": "Mã bảo vệ không chính xác"}}).encode("utf-8")
            start_response("401 Unauthorized", [("Content-Type", "application/json"), *CORS_HEADERS])
        return [payload]

    if path == "/api/auth/logout" and method == "POST":
        cookie = "cuti_token=; Path=/; Max-Age=0; SameSite=Lax"
        payload = json.dumps({"ok": False, "token": ""}).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json"), ("Set-Cookie", cookie), *CORS_HEADERS])
        return [payload]

    # Auth enforcement
    if settings.auth_secret and not is_auth:
        payload = json.dumps({"error": {"code": "unauthorized", "message": "Yêu cầu xác thực quyền truy cập"}}).encode("utf-8")
        start_response("401 Unauthorized", [("Content-Type", "application/json"), *CORS_HEADERS])
        return [payload]

    # Pricing config routes
    pricing_route = path in {"/api/pricing-config", "/api/pricing-config/preview"}
    if pricing_route:
        origin = headers.get("Origin")
        if origin and not _local_origin(origin) and not is_auth:
            payload = json.dumps({"error": {"code": "origin_not_allowed", "message": "pricing configuration is local-only"}}).encode("utf-8")
            start_response("403 Forbidden", [("Content-Type", "application/json"), *CORS_HEADERS])
            return [payload]
        from cuti.api_pricing import get as pricing_get, write as pricing_write
        status, data = pricing_get(settings) if method == "GET" else pricing_write(settings, method, body or {})
        payload = json.dumps(data, default=str).encode("utf-8")
        start_response(f"{status} {HTTPStatus(status).phrase}", [("Content-Type", "application/json"), *CORS_HEADERS])
        return [payload]

    # Telegram media streaming
    parts = [urllib.parse.unquote(p) for p in path.strip("/").split("/") if p]
    if len(parts) == 5 and parts[:3] == ["api", "media", "lots"] and parts[4] == "cover":
        lot_id = parts[3]
        conn = connect(settings.db_path)
        try:
            image = fetch_lot_image(conn, lot_id)
        finally:
            conn.close()
        if not image or image["state"] != "ready" or not image["telegram_file_id"]:
            payload = json.dumps({"error": {"code": "cover_missing", "message": "Cover media missing or not ready"}}).encode("utf-8")
            start_response("404 Not Found", [("Content-Type", "application/json"), *CORS_HEADERS])
            return [payload]
        try:
            token, _ = require_telegram_credentials(settings)
            file_path = telegram_get_file(settings, image["telegram_file_id"])
            file_url = f"{settings.telegram_api_base}/file/bot{token}/{urllib.parse.quote(file_path, safe='/')}"
            with urllib.request.urlopen(file_url, timeout=settings.http_timeout_seconds) as resp:
                image_data = resp.read()
                content_type = resp.headers.get("Content-Type", "image/jpeg")
            start_response("200 OK", [
                ("Content-Type", content_type),
                ("Cache-Control", "public, max-age=86400, immutable"),
                *CORS_HEADERS,
            ])
            return [image_data]
        except Exception as exc:
            payload = json.dumps({"error": {"code": "telegram_unavailable", "message": str(exc)}}).encode("utf-8")
            start_response("502 Bad Gateway", [("Content-Type", "application/json"), *CORS_HEADERS])
            return [payload]

    # Core REST API dispatch
    conn = connect(settings.db_path)
    try:
        ensure_catalog(conn, load_catalog(settings.rules_path.parent / "catalog.json"), datetime.now(timezone.utc))
        if method == "GET":
            status, data = get(conn, settings, path, query_params(query))
        else:
            status, data = write(conn, settings, method, path, body)
    except ApiError as exc:
        status, data = exc.status, error_payload(exc)
    except Exception as exc:
        status, data = 500, {"error": {"code": "system_error", "message": str(exc), "traceback": traceback.format_exc()}}
    finally:
        conn.close()

    payload = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
    status_str = f"{status} {HTTPStatus(status).phrase}" if status in HTTPStatus._value2member_map_ else f"{status} OK"
    start_response(status_str, [("Content-Type", "application/json; charset=utf-8"), *CORS_HEADERS])
    return [payload]


class handler(CutiApiHandler):
    """Fallback handler for BaseHTTPRequestHandler runtimes."""
    def _dispatch(self, method: str, body: object | None = None) -> None:
        matched = self.headers.get("x-matched-path")
        if matched and matched.startswith("/api"):
            query = urllib.parse.urlparse(self.path).query
            self.path = matched + (f"?{query}" if query else "")
        ensure_database_synced(TMP_DB)
        super()._dispatch(method, body)
