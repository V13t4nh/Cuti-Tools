"""Vercel Serverless Function entrypoint for CUTI REST API."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# In Vercel serverless environment, writable directory is /tmp
TMP_DB = Path("/tmp/auctions.db")
os.environ.setdefault("CUTI_DB_PATH", str(TMP_DB))
os.environ.setdefault("CUTI_HOME", str(PROJECT_ROOT))

from cuti.r2 import ensure_database_synced
from cuti.server import CutiApiHandler


class handler(CutiApiHandler):
    """Vercel Serverless Request Handler."""

    def _dispatch(self, method: str, body: object | None = None) -> None:
        # Ensure database is available before handling request
        ensure_database_synced(TMP_DB)
        super()._dispatch(method, body)
