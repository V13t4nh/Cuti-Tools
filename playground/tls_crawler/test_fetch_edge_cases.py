"""Comprehensive edge-case test suite for src/cuti/fetch.py.
Tests local file errors, credential masking, profile rotation on 403,
fail-fast on missing dependency, proxy resolution, and size limits.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root and src to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import cuti.fetch as fetch
from cuti.errors import FetchError


class FetchEdgeCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="cuti-fetch-edge-"))
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # --- 1. SCHEME & PATH NORMALIZATION EDGE CASES ---
    def test_empty_location_raises_typed_error(self) -> None:
        with self.assertRaises(FetchError) as ctx:
            fetch.to_url("")
        self.assertIn("empty source location", str(ctx.exception))

    def test_unsupported_scheme_raises_typed_error(self) -> None:
        for scheme in ["ftp://example.com/file", "gopher://example.com", "ws://example.com"]:
            with self.subTest(scheme=scheme):
                with self.assertRaises(FetchError) as ctx:
                    fetch.to_url(scheme)
                self.assertIn("unsupported scheme", str(ctx.exception))

    def test_relative_links_resolve_edge_cases(self) -> None:
        self.assertEqual(
            fetch.resolve("https://example.com/a/b/index.html", "../c/page.html"),
            "https://example.com/a/c/page.html",
        )
        self.assertEqual(
            fetch.resolve("file:///C:/cuti/page-1.html", "page-2.html"),
            "file:///C:/cuti/page-2.html",
        )

    # --- 2. LOCAL FILE PROTOCOL EDGE CASES ---
    def test_missing_local_file_raises_fetch_error(self) -> None:
        missing = self.temp_dir / "does_not_exist.html"
        with self.assertRaises(FetchError):
            fetch.fetch_text(str(missing), timeout_seconds=5)

    def test_local_file_exceeding_max_bytes_raises_fetch_error(self) -> None:
        large_file = self.temp_dir / "large.txt"
        large_file.write_bytes(b"X" * 100)
        with self.assertRaises(FetchError) as ctx:
            fetch.fetch_text(str(large_file), timeout_seconds=5, max_bytes=50)
        self.assertIn("exceeds 50 bytes", str(ctx.exception))

    def test_local_file_invalid_utf8_raises_fetch_error(self) -> None:
        bad_utf8 = self.temp_dir / "bad_utf8.bin"
        bad_utf8.write_bytes(b"\x80\x81\x82\xff\xfe")
        with self.assertRaises(FetchError) as ctx:
            fetch.fetch_text(str(bad_utf8), timeout_seconds=5)
        self.assertIn("not valid UTF-8", str(ctx.exception))

    def test_fetch_json_invalid_json_raises_fetch_error(self) -> None:
        broken_json = self.temp_dir / "broken.json"
        broken_json.write_text("{ unquoted_key: 123 ", encoding="utf-8")
        with self.assertRaises(FetchError) as ctx:
            fetch.fetch_json(str(broken_json), timeout_seconds=5)
        self.assertIn("invalid JSON", str(ctx.exception))

    # --- 3. CREDENTIAL & PROXY SENSITIVE DATA MASKING ---
    def test_safe_url_masks_telegram_tokens(self) -> None:
        raw_url = "https://api.telegram.org/bot123456789:ABCdefGHI_jklMNO/sendMessage"
        safe = fetch._safe_url(raw_url)
        self.assertNotIn("ABCdefGHI_jklMNO", safe)
        self.assertIn("/bot<redacted>/", safe)

    def test_safe_url_masks_proxy_credentials(self) -> None:
        raw_proxy_url = "http://myuser:supersecret_password@proxy.provider.com:8080/data"
        safe = fetch._safe_url(raw_proxy_url)
        self.assertNotIn("supersecret_password", safe)
        self.assertIn("http://myuser:<redacted>@proxy.provider.com:8080/data", safe)

    # --- 4. SCENARIO 2: PROXY RESOLUTION FROM ENV ---
    def test_proxy_extracted_from_environment(self) -> None:
        with patch.dict(os.environ, {"HTTPS_PROXY": "http://127.0.0.1:8888"}):
            proxy_cfg = fetch._get_proxy()
            self.assertIsNotNone(proxy_cfg)
            self.assertEqual(proxy_cfg["https"], "http://127.0.0.1:8888")
            self.assertEqual(proxy_cfg["http"], "http://127.0.0.1:8888")

    def test_proxy_none_when_env_empty(self) -> None:
        clean_env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
        with patch.dict(os.environ, clean_env, clear=True):
            self.assertIsNone(fetch._get_proxy())

    # --- 5. SCENARIO 2: WAF 403 PROFILE ROTATION ---
    def test_403_triggers_profile_rotation_and_succeeds_on_retry(self) -> None:
        fetch._CURRENT_PROFILE_IDX = 0
        fetch._SESSIONS.clear()

        # Create mock responses
        resp_403 = MagicMock(status_code=403, content=b"Access Denied")
        resp_200 = MagicMock(status_code=200, content=b"<html>Success after rotation</html>")

        mock_session_chrome = MagicMock()
        mock_session_chrome.get.return_value = resp_403

        mock_session_safari = MagicMock()
        mock_session_safari.get.return_value = resp_200

        def fake_get_session(profile: str):
            if profile == "chrome124":
                return mock_session_chrome
            elif profile == "safari17_0":
                return mock_session_safari
            return mock_session_chrome

        with patch("cuti.fetch._get_session_for_profile", side_effect=fake_get_session):
            content = fetch.fetch_text("https://example.com/lot/1", timeout_seconds=10)

        self.assertEqual(content, "<html>Success after rotation</html>")
        mock_session_chrome.get.assert_called_once()
        mock_session_safari.get.assert_called_once()
        self.assertEqual(fetch.TLS_PROFILES[fetch._CURRENT_PROFILE_IDX], "safari17_0")

    def test_403_raises_fetch_error_if_all_profiles_fail(self) -> None:
        fetch._CURRENT_PROFILE_IDX = 0
        fetch._SESSIONS.clear()

        resp_403 = MagicMock(status_code=403, content=b"Access Denied")
        mock_session = MagicMock()
        mock_session.get.return_value = resp_403

        with patch("cuti.fetch._get_session_for_profile", return_value=mock_session):
            with self.assertRaises(FetchError) as ctx:
                fetch.fetch_text("https://example.com/lot/blocked", timeout_seconds=10)

        self.assertIn("HTTP 403", str(ctx.exception))
        # Verified it attempted rotation (called at least twice)
        self.assertEqual(mock_session.get.call_count, 2)

    # --- 6. NO-FALLBACK / FAIL FAST ON MISSING DEPENDENCY ---
    def test_missing_curl_cffi_raises_fetch_error_without_fallback(self) -> None:
        with patch("cuti.fetch.curl_requests", None), patch(
            "cuti.fetch._IMPORT_ERROR", ImportError("No module named 'curl_cffi'")
        ):
            with self.assertRaises(FetchError) as ctx:
                fetch._get_session_for_profile("chrome124")
            self.assertIn("curl-cffi is required", str(ctx.exception))

    # --- 7. REMOTE MAX BYTES & STATUS CODE EDGE CASES ---
    def test_remote_exceeding_max_bytes_raises_fetch_error(self) -> None:
        resp_too_large = MagicMock(status_code=200, content=b"A" * 500)
        mock_sess = MagicMock()
        mock_sess.get.return_value = resp_too_large

        with patch("cuti.fetch._get_session_for_profile", return_value=mock_sess):
            with self.assertRaises(FetchError) as ctx:
                fetch.fetch_text("https://example.com/huge", timeout_seconds=10, max_bytes=200)
            self.assertIn("exceeds 200 bytes", str(ctx.exception))

    def test_remote_500_raises_fetch_error(self) -> None:
        resp_500 = MagicMock(status_code=500, content=b"Internal Server Error")
        mock_sess = MagicMock()
        mock_sess.get.return_value = resp_500

        with patch("cuti.fetch._get_session_for_profile", return_value=mock_sess):
            with self.assertRaises(FetchError) as ctx:
                fetch.fetch_text("https://example.com/server_error", timeout_seconds=10)
            self.assertIn("HTTP 500", str(ctx.exception))

    # --- 8. PROBE_URL & POST_JSON EDGE CASES ---
    def test_probe_url_remote_rotates_on_403(self) -> None:
        fetch._CURRENT_PROFILE_IDX = 0
        resp_403 = MagicMock(status_code=403, url="https://example.com/probe")
        resp_200 = MagicMock(status_code=200, url="https://example.com/probe/final")

        sess1 = MagicMock()
        sess1.get.return_value = resp_403
        sess2 = MagicMock()
        sess2.get.return_value = resp_200

        with patch("cuti.fetch._get_session_for_profile", side_effect=[sess1, sess2]):
            code, final_url = fetch.probe_url("https://example.com/probe", timeout_seconds=10)

        self.assertEqual(code, 200)
        self.assertEqual(final_url, "https://example.com/probe/final")

    def test_post_json_remote_rotates_on_403(self) -> None:
        fetch._CURRENT_PROFILE_IDX = 0
        resp_403 = MagicMock(status_code=403, content=b"Access Denied")
        resp_200 = MagicMock(status_code=200, content=b'{"ok": true}', json=lambda: {"ok": True})

        sess1 = MagicMock()
        sess1.post.return_value = resp_403
        sess2 = MagicMock()
        sess2.post.return_value = resp_200

        with patch("cuti.fetch._get_session_for_profile", side_effect=[sess1, sess2]):
            res = fetch.post_json("https://example.com/api", payload={"test": 1}, timeout_seconds=10)

        self.assertEqual(res, {"ok": True})


if __name__ == "__main__":
    unittest.main()
