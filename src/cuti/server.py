"""Small HTTP adapter for the local CUTI API."""

from __future__ import annotations

import json
import math
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .api import ApiError, error_payload, get, query_params, write
from .config import load_settings
from .errors import MediaUploadError
from .storage import connect, ensure_catalog, fetch_lot_image, load_catalog
from .telegram_media import require_telegram_credentials, telegram_get_file

_MAX_BODY = 256 * 1024


def _json_constant(value: str) -> object:
    raise ValueError(f"invalid JSON constant {value}")


def _json_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("JSON number is not finite")
    return number


def _local_origin(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1", "::1"} and not parsed.username


class CutiApiHandler(BaseHTTPRequestHandler):
    """Translate HTTP requests to typed application handlers."""

    def _headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send(self, status: int, data: dict | list) -> None:
        try:
            payload = json.dumps(data, default=str, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError):
            status = 500
            payload = b'{"error":{"code":"non_finite_response","message":"Response contains an invalid number"}}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._headers()
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._headers()
        self.end_headers()

    def _dispatch(self, method: str, body: object | None = None) -> None:
        parsed = urlparse(self.path)
        pricing_route = parsed.path.rstrip("/") in {"/api/pricing-config", "/api/pricing-config/preview"}
        if pricing_route:
            origin = self.headers.get("Origin")
            if origin and not _local_origin(origin):
                self._send(403, {"error": {"code": "origin_not_allowed", "message": "pricing configuration is local-only"}})
                return
        settings = load_settings()
        pricing_path = parsed.path.rstrip("/")
        if (pricing_path == "/api/pricing-config" and method == "GET") or (pricing_path == "/api/pricing-config/preview" and method == "POST") or (pricing_path == "/api/pricing-config" and method == "PUT"):
            from .api_pricing import get as pricing_get, write as pricing_write
            status, payload = pricing_get(settings) if method == "GET" else pricing_write(settings, method, body or {})
            self._send(status, payload)
            return
        conn = connect(settings.db_path)
        try:
            ensure_catalog(conn, load_catalog(settings.rules_path.parent / "catalog.json"), datetime.now(timezone.utc))
            try:
                if method == "GET":
                    status, payload = get(conn, settings, parsed.path.rstrip("/"), query_params(parsed.query))
                else:
                    status, payload = write(conn, settings, method, parsed.path.rstrip("/"), body)
            except ApiError as exc:
                self._send(exc.status, error_payload(exc))
                return
            except Exception as exc:
                self._send(500, {"error": {"code": "system_error", "message": "Request could not be completed", "details": str(exc)}})
                return
        finally:
            conn.close()
        self._send(status, payload)

    def do_GET(self) -> None:
        parts = [urllib.parse.unquote(part) for part in urlparse(self.path).path.strip("/").split("/") if part]
        if len(parts) == 5 and parts[:3] == ["api", "media", "lots"] and parts[4] == "cover":
            self._stream_cover(parts[3])
            return
        self._dispatch("GET")

    def _stream_cover(self, lot_id: str) -> None:
        settings = load_settings()
        conn = connect(settings.db_path)
        try:
            image = fetch_lot_image(conn, lot_id)
        finally:
            conn.close()
        if image is None:
            self._send(404, {"error": {"code": "cover_missing", "message": "Cover media is missing"}})
            return
        if image["state"] != "ready" or not image["telegram_file_id"]:
            self._send(409, {"error": {"code": "cover_not_ready", "message": "Cover media is not ready", "state": image["state"]}})
            return
        try:
            token, _ = require_telegram_credentials(settings)
            file_path = telegram_get_file(settings, image["telegram_file_id"])
            file_url = f"{settings.telegram_api_base}/file/bot{token}/{urllib.parse.quote(file_path, safe='/')}"
            response = urllib.request.urlopen(file_url, timeout=settings.http_timeout_seconds)
        except (MediaUploadError, urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
            self._send(502, {"error": {"code": "telegram_media_unavailable", "message": "Telegram media could not be retrieved"}})
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", response.headers.get("Content-Type", "application/octet-stream"))
            length = response.headers.get("Content-Length")
            if length:
                self.send_header("Content-Length", length)
            self.send_header("Cache-Control", "public, max-age=86400, immutable")
            self._headers()
            self.end_headers()
            while chunk := response.read(64 * 1024):
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.close_connection = True
        finally:
            response.close()

    def do_POST(self) -> None:
        self._dispatch_body("POST")

    def do_PATCH(self) -> None:
        self._dispatch_body("PATCH")

    def do_PUT(self) -> None:
        self._dispatch_body("PUT")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE", {})

    def _dispatch_body(self, method: str) -> None:
        try:
            body = self._body()
        except ApiError as exc:
            self._send(exc.status, error_payload(exc))
            return
        self._dispatch(method, body)

    def _body(self) -> object:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length < 0 or length > _MAX_BODY:
                raise ApiError(413, "request_too_large", "Request body is too large")
            return json.loads(self.rfile.read(length).decode("utf-8"), parse_constant=_json_constant, parse_float=_json_float) if length else {}
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError(400, "invalid_json", "Request body is not valid JSON") from exc

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("[CUTI API] " + (format % args) + "\n")


def run_server(port: int = 8000, host: str = "127.0.0.1") -> None:
    """Start the CUTI REST API server."""
    load_settings()
    httpd = ThreadingHTTPServer((host, port), CutiApiHandler)
    print(f"[CUTI API] Server running on http://{host}:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[CUTI API] Server shutting down...", flush=True)
        httpd.server_close()


if __name__ == "__main__":
    run_server(port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
