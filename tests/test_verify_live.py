"""Offline checks for the production-parity verifier's source gate."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.verify_live import configured_sources


class VerifyLiveSourceGateTests(unittest.TestCase):
    def test_missing_sources_are_reported_without_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            configured, missing = configured_sources(
                project_root=Path(directory), env={}
            )
        self.assertEqual(configured, {"CUTI_LOTS_SOURCE_URL": "", "CUTI_CATAWIKI_API_BASE": ""})
        self.assertEqual(missing, ["CUTI_LOTS_SOURCE_URL", "CUTI_CATAWIKI_API_BASE"])

    def test_dotenv_values_count_as_explicit_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "CUTI_LOTS_SOURCE_URL=https://example.test/lots\n"
                "CUTI_CATAWIKI_API_BASE=https://example.test\n",
                encoding="utf-8",
            )
            configured, missing = configured_sources(project_root=root, env={})
        self.assertEqual(missing, [])
        self.assertEqual(configured["CUTI_LOTS_SOURCE_URL"], "https://example.test/lots")

