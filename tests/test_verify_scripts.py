"""Offline contracts for the two verification entry points."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.verify import _source_loc_max
from scripts.verify_live import _run_pipeline


class VerifyScriptTests(unittest.TestCase):
    def test_verify_reports_the_real_source_line_maximum(self) -> None:
        self.assertLessEqual(_source_loc_max(), 230)

    def test_live_pipeline_has_ingest_cap_and_settle_step(self) -> None:
        settings = SimpleNamespace(
            lots_source_url="https://example.test/lots",
            catawiki_api_base="https://example.test",
        )
        calls: list[tuple[str, list[str]]] = []

        def fake_run(name: str, argv: list[str], env: dict[str, str], log_dir: Path) -> int:
            calls.append((name, argv))
            return 0

        with tempfile.TemporaryDirectory() as directory:
            with patch("scripts.verify_live._run_cli_logged", side_effect=fake_run):
                self.assertEqual(_run_pipeline(settings, Path(directory)), 0)

        self.assertEqual([name for name, _argv in calls], [
            "init-db", "ingest", "settle", "evaluate", "liquidity", "report", "status"
        ])
        ingest_argv = calls[1][1]
        self.assertEqual(ingest_argv[-3:], ["ingest", "--max-lots", "50"])


if __name__ == "__main__":
    unittest.main()
