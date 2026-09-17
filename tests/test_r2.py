"""Unit tests for Cloudflare R2 / S3 SigV4 sync helper."""

from __future__ import annotations

import unittest
from pathlib import Path

from cuti.r2 import (
    _build_sigv4_request,
    _get_signature_key,
    ensure_database_synced,
    get_r2_config,
)


class R2SyncTests(unittest.TestCase):
    def test_get_r2_config_missing(self) -> None:
        self.assertIsNone(get_r2_config({}))
        self.assertIsNone(get_r2_config({"R2_ENDPOINT_URL": "https://example.com"}))

    def test_get_r2_config_valid(self) -> None:
        cfg = get_r2_config(
            {
                "R2_ENDPOINT_URL": "https://acc.r2.cloudflarestorage.com",
                "R2_ACCESS_KEY_ID": "key123",
                "R2_SECRET_ACCESS_KEY": "secret456",
            }
        )
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["bucket"], "cuti-data")
        self.assertEqual(cfg["key"], "auctions.db")

    def test_sigv4_request_structure(self) -> None:
        req = _build_sigv4_request(
            method="GET",
            endpoint="https://account.r2.cloudflarestorage.com",
            bucket="my-bucket",
            key="auctions.db",
            access_key="test_key",
            secret_key="test_secret",
        )
        self.assertEqual(req.get_method(), "GET")
        headers = {k.lower(): v for k, v in req.header_items()}
        self.assertIn("authorization", headers)
        auth = headers["authorization"]
        self.assertTrue(auth.startswith("AWS4-HMAC-SHA256 Credential=test_key/"))
        self.assertIn("SignedHeaders=host;x-amz-content-sha256;x-amz-date", auth)
        self.assertIn("x-amz-date", headers)
        self.assertIn("x-amz-content-sha256", headers)

    def test_ensure_database_synced_unconfigured(self) -> None:
        import os
        orig = dict(os.environ)
        try:
            for k in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
                os.environ.pop(k, None)
            self.assertFalse(ensure_database_synced(Path("/nonexistent/path/db.sqlite")))
        finally:
            os.environ.clear()
            os.environ.update(orig)
