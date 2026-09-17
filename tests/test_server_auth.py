"""Unit tests for server authentication."""

from __future__ import annotations

import json
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import threading

from cuti.server import run_server
from support import ProjectTestCase


class ServerAuthTests(ProjectTestCase):
    def test_auth_enforcement_when_secret_set(self) -> None:
        settings = self.make_settings(CUTI_AUTH_SECRET="test_secret_123")
        # Test helper directly without needing full socket server
        from cuti.server import _check_auth
        # Empty token -> fails
        headers = {"Authorization": ""}
        self.assertFalse(_check_auth(headers, "", settings.auth_secret))

        # Bearer token -> passes
        headers = {"Authorization": "Bearer test_secret_123"}
        self.assertTrue(_check_auth(headers, "", settings.auth_secret))

        # Query token -> passes
        headers = {}
        self.assertTrue(_check_auth(headers, "token=test_secret_123", settings.auth_secret))

        # Cookie token -> passes
        headers = {"Cookie": "other=1; cuti_token=test_secret_123; foo=bar"}
        self.assertTrue(_check_auth(headers, "", settings.auth_secret))

        # Invalid token -> fails
        headers = {"Authorization": "Bearer wrong_secret"}
        self.assertFalse(_check_auth(headers, "", settings.auth_secret))

    def test_auth_disabled_when_secret_empty(self) -> None:
        settings = self.make_settings(CUTI_AUTH_SECRET="")
        from cuti.server import _check_auth
        # When secret is empty, all requests pass
        headers = {}
        self.assertTrue(_check_auth(headers, "", settings.auth_secret))


if __name__ == "__main__":
    unittest.main()
