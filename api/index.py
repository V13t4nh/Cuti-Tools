"""Vercel Serverless Function entrypoint for CUTI REST API."""

from __future__ import annotations

import json
import os
import sys
import traceback
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

try:
    from cuti.r2 import ensure_database_synced
    from cuti.server import CutiApiHandler

    class handler(CutiApiHandler):
        """Vercel Serverless Request Handler."""

        def _dispatch(self, method: str, body: object | None = None) -> None:
            try:
                # If Vercel rewrote the path to /api, restore original path from x-matched-path
                matched = self.headers.get("x-matched-path")
                if matched and matched.startswith("/api"):
                    from urllib.parse import urlparse
                    query = urlparse(self.path).query
                    self.path = matched + (f"?{query}" if query else "")

                ensure_database_synced(TMP_DB)
                super()._dispatch(method, body)
            except Exception as exc:
                self._send(500, {
                    "error": {
                        "code": "serverless_error",
                        "message": str(exc),
                        "traceback": traceback.format_exc(),
                    }
                })

except Exception as startup_err:
    class handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._error()

        def do_POST(self) -> None:
            self._error()

        def do_OPTIONS(self) -> None:
            self._error()

        def _error(self) -> None:
            payload = json.dumps({
                "error": {
                    "code": "startup_failed",
                    "message": str(startup_err),
                    "traceback": traceback.format_exc(),
                }
            }).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
