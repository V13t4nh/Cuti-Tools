"""Offline contracts for the two verification entry points."""

from __future__ import annotations

import tempfile
import unittest
import hashlib
import sqlite3
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.verify import (
    FrozenFileError,
    _alerts_sent,
    _environment_trace,
    _frozen_markers,
    _frozen_sha256,
    _live_fixture_count,
    _source_loc_max,
)
from scripts.verify import main
from scripts.verify_live import _run_pipeline


class VerifyScriptTests(unittest.TestCase):
    def test_empty_cuti_environment_is_explicitly_marked(self) -> None:
        class Log:
            def __init__(self) -> None:
                self.lines: list[str] = []

            def line(self, text: str = "") -> None:
                self.lines.append(text)

            def write(self, text: str) -> None:
                self.lines.append(text)

        log = Log()
        with patch("scripts.verify.subprocess.run") as run:
            run.return_value.stdout = ""
            _environment_trace(log, {})
        self.assertIn("CUTI_ENV_NAMES=(none)", log.lines)

    def test_alerts_sent_reads_sent_rows_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "alerts.db"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("CREATE TABLE alert_outbox (status TEXT)")
                conn.executemany(
                    "INSERT INTO alert_outbox(status) VALUES (?)",
                    [("sent",), ("pending",), ("dead",), ("sent",)],
                )
                conn.commit()
            finally:
                conn.close()
            self.assertEqual(_alerts_sent(db_path), 2)

    def test_verify_reports_the_real_source_line_maximum(self) -> None:
        self.assertLessEqual(_source_loc_max(), 230)

    def test_frozen_sha256_reads_exact_temp_file_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frozen.bin"
            payload = b"frozen bytes\x00\xff"
            path.write_bytes(payload)
            expected = hashlib.sha256(payload).hexdigest()
            self.assertEqual(_frozen_sha256(path), expected)

    def test_frozen_sha256_missing_file_is_typed_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FrozenFileError):
                _frozen_sha256(Path(directory) / "missing.py")

    def test_frozen_markers_use_deterministic_paths_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = (
                "src/cuti/pricing.py",
                "src/cuti/storage/schema_ddl.py",
                "config/rules.json",
            )
            for relative in paths:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(relative.encode("ascii"))
            markers = _frozen_markers(root)
            self.assertEqual([line.split()[1] for line in markers], list(paths))
            self.assertEqual(len(markers), 3)

    def test_live_fixture_count_is_zero_without_fixture_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("scripts.verify.PROJECT_ROOT", Path(directory)):
                self.assertEqual(_live_fixture_count(), 0)

    def test_live_fixture_count_includes_only_real_html_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture_dir = Path(directory) / "tests" / "fixtures" / "live"
            fixture_dir.mkdir(parents=True)
            (fixture_dir / "106019970.html").write_text("<html>", encoding="utf-8")
            (fixture_dir / "notes.txt").write_text("not a fixture", encoding="utf-8")
            (fixture_dir / "directory.html").mkdir()
            with patch("scripts.verify.PROJECT_ROOT", Path(directory)):
                self.assertEqual(_live_fixture_count(), 1)

    def test_verify_main_prints_and_logs_zero_live_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (
                "src/cuti/pricing.py",
                "src/cuti/storage/schema_ddl.py",
                "config/rules.json",
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(relative.encode("ascii"))
            output = StringIO()
            with patch("scripts.verify.PROJECT_ROOT", root), patch(
                "scripts.verify._environment_trace"
            ), patch("scripts.verify._run"), patch(
                "scripts.verify._source_loc_max", return_value=0
            ), redirect_stdout(output):
                self.assertEqual(main(), 0)

            log_path = root / "var" / "verify" / date.today().isoformat() / "verify.log"
            log = log_path.read_text(encoding="utf-8")
            self.assertIn("LIVE_FIXTURES=0\n", log)
            self.assertIn("ALERTS_SENT=0\n", log)
            self.assertIn("LIVE_FIXTURES=0\n", output.getvalue())
            self.assertIn("ALERTS_SENT=0\n", output.getvalue())

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
