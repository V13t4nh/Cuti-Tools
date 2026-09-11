"""Tests for CUTI Ops Control Deck (TUI) and subprocess supervisor."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from cuti_tui import (
    SubprocessTask,
    SystemMetrics,
    is_port_open,
    kill_process_tree,
    query_metrics,
)


class TestCutiTui(unittest.TestCase):
    """Test suite for TUI helper functions and process supervisor."""

    def test_is_port_open_returns_bool(self) -> None:
        """Verify port checker returns a boolean and handles closed ports cleanly."""
        # Port 65432 is typically closed
        result = is_port_open(65432)
        self.assertIsInstance(result, bool)

    def test_query_metrics(self) -> None:
        """Verify query_metrics returns a valid SystemMetrics dataclass."""
        metrics = query_metrics()
        self.assertIsInstance(metrics, SystemMetrics)
        self.assertGreaterEqual(metrics.lots_count, 0)
        self.assertGreaterEqual(metrics.pending_images, 0)
        self.assertIsInstance(metrics.api_active, bool)
        self.assertIsInstance(metrics.vite_active, bool)

    def test_subprocess_task_streaming_and_exit(self) -> None:
        """Verify SubprocessTask streams stdout lines and fires on_exit."""
        lines: list[str] = []
        exit_codes: list[int] = []

        def on_line(tag: str, line: str) -> None:
            lines.append(f"{tag}:{line}")

        def on_exit(tag: str, code: int) -> None:
            exit_codes.append(code)

        task = SubprocessTask(
            name="test_worker",
            tag="TEST",
            cmd=[sys.executable, "-c", "import sys; print('HELLO_TUI'); sys.stdout.flush()"],
            cwd=PROJECT_ROOT,
            on_line=on_line,
            on_exit=on_exit,
        )
        task.start()

        # Wait up to 5 seconds for completion
        deadline = time.monotonic() + 5.0
        while not exit_codes and time.monotonic() < deadline:
            time.sleep(0.1)

        self.assertEqual(exit_codes, [0])
        self.assertIn("TEST:HELLO_TUI", lines)

    def test_kill_process_tree(self) -> None:
        """Verify kill_process_tree terminates a running subprocess."""
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=PROJECT_ROOT,
        )
        try:
            self.assertIsNone(proc.poll())
            kill_process_tree(proc.pid)
            # Process should be terminated
            proc.wait(timeout=3.0)
            self.assertIsNotNone(proc.poll())
        finally:
            if proc.poll() is None:
                proc.kill()

    def test_tui_check_flag(self) -> None:
        """Verify cuti_tui.py --check executes and returns code 0."""
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "cuti_tui.py"), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("TUI Environment OK", result.stdout)


    def test_image_worker_until_empty(self) -> None:
        """Verify run_image_worker.py --until-empty exits cleanly when queue is idle."""
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "run_image_worker.py"), "--until-empty"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Worker completed", result.stdout)


class TestCutiControlAppAsync(unittest.IsolatedAsyncioTestCase):
    """Async pilot tests for Textual CutiControlApp."""

    async def test_app_mount_and_initial_widgets(self) -> None:
        from cuti_tui import CutiControlApp, TEXTUAL_AVAILABLE
        if not TEXTUAL_AVAILABLE:
            self.skipTest("textual is not installed")

        app = CutiControlApp()
        async with app.run_test() as pilot:
            # Check presence of buttons in 2-column grid
            btn_dev = app.query_one("#btn_dev")
            self.assertIsNotNone(btn_dev)
            btn_pipeline = app.query_one("#btn_pipeline")
            self.assertIsNotNone(btn_pipeline)
            btn_copy = app.query_one("#btn_copy")
            self.assertIsNotNone(btn_copy)
            btn_stop = app.query_one("#btn_stop")
            self.assertIsNotNone(btn_stop)

            # Check presence of log panes & word wrap
            log_all = app.query_one("#log_all")
            self.assertIsNotNone(log_all)
            self.assertTrue(log_all.wrap)
            log_api = app.query_one("#log_api")
            self.assertIsNotNone(log_api)
            self.assertTrue(log_api.wrap)

            # Test toggle word wrap
            app.action_toggle_wrap()
            self.assertFalse(log_all.wrap)
            app.action_toggle_wrap()
            self.assertTrue(log_all.wrap)

            # Test log buffer caching & copy
            app._log("SYSTEM", "SAMPLE_LOG_ENTRY")
            self.assertTrue(any("SAMPLE_LOG_ENTRY" in line for line in app.log_buffers["tab_all"]))

            # Test copy active log action
            app.action_copy_active_log()

            # Test clear active log action
            app.action_clear_active_log()
            self.assertFalse(any("SAMPLE_LOG_ENTRY" in line for line in app.log_buffers["tab_all"]))
            self.assertTrue(any("Đã xóa log" in line for line in app.log_buffers["tab_all"]))

            # Check quit binding
            await pilot.press("q")


if __name__ == "__main__":
    unittest.main()

