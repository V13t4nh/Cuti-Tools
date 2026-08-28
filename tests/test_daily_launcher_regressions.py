"""Offline launcher lifecycle regressions; no child process or network is used."""

from __future__ import annotations

import tempfile
import unittest
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import scripts.run_daily as daily
from cuti.errors import FetchError
from daily_crawl_harness import block_network
from process_lock import ProcessLockBusy


NOW = datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc)


class DailyLauncherLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="cuti-daily-launcher-"))
        self.addCleanup(self._cleanup)
        self.network_guard = block_network()
        self.network_guard.__enter__()
        self.addCleanup(self.network_guard.__exit__, None, None, None)
        self.settings = SimpleNamespace(
            db_path=self.temp_dir / "isolated.db",
            rules_path=self.temp_dir / "rules.json",
        )

    def _cleanup(self) -> None:
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_busy_daily_lock_returns_nonzero_without_waiting(self) -> None:
        with patch("scripts.run_daily.load_rules", return_value=object()), patch(
            "scripts.run_daily.process_lock",
            side_effect=ProcessLockBusy("daily run is already running"),
        ):
            code = daily.run_daily(settings=self.settings, now=NOW)
        self.assertEqual(code, 2)

    def test_empty_queue_does_not_mask_busy_uploader(self) -> None:
        """An uploader singleton conflict is an error even when no rows are pending."""
        with patch("scripts.run_daily.load_rules", return_value=object()), patch(
            "scripts.run_daily.process_lock", side_effect=lambda *_args: nullcontext()
        ), patch(
            "scripts.run_daily.start_worker_process",
            side_effect=ProcessLockBusy("image worker is already running"),
        ):
            code = daily.run_daily(settings=self.settings, now=NOW)
        self.assertEqual(code, 2)

    def test_worker_busy_exit_does_not_wait_forever_for_pending_queue(self) -> None:
        worker = SimpleNamespace(is_alive=lambda: False, exitcode=2)
        with patch("scripts.run_daily.queue_is_drained", return_value=False):
            result = daily._wait_for_drain(
                object(), worker, True, lambda _seconds: self.fail("busy worker was polled forever")
            )
        self.assertIsNotNone(result)
        self.assertIn("worker", result)

    def test_shutdown_closes_parent_pipe_and_joins_before_any_terminate(self) -> None:
        events: list[str] = []

        class Parent:
            closed = False

            def send(self, message: str) -> None:
                events.append(f"send:{message}")

            def close(self) -> None:
                events.append("close_pipe")
                self.closed = True

        parent = Parent()

        class Process:
            def __init__(self) -> None:
                self.alive = True

            def is_alive(self) -> bool:
                return self.alive

            def join(self, timeout: float | None = None) -> None:
                del timeout
                events.append("join")
                self.alive = False

            def terminate(self) -> None:
                events.append("terminate")

            def kill(self) -> None:
                events.append("kill")

        process = Process()
        report = SimpleNamespace(candidates=0, queued=0, missing=(), failures=())
        fake_conn = object()
        with patch("scripts.run_daily.load_rules", return_value=object()), patch(
            "scripts.run_daily.process_lock", side_effect=lambda *_args: nullcontext()
        ), patch(
            "scripts.run_daily.connect", side_effect=lambda _path: nullcontext(fake_conn)
        ), patch(
            "scripts.run_daily.start_worker_process", return_value=(process, parent)
        ), patch(
            "scripts.run_daily._run_producer", return_value=(True, [])
        ), patch(
            "scripts.run_daily.reconcile_missing_lot_images", return_value=report
        ), patch(
            "scripts.run_daily._wait_for_drain", return_value=None
        ), patch(
            "scripts.run_daily.queue_state", return_value={}
        ), patch(
            "scripts.run_daily.count_lot_images", return_value={"permanent_error": 0}
        ):
            code = daily.run_daily(settings=self.settings, now=NOW)
        self.assertEqual(code, 0)
        self.assertIn("send:stop", events)
        self.assertIn("close_pipe", events)
        self.assertIn("join", events)
        if "terminate" in events:
            self.assertLess(events.index("send:stop"), events.index("terminate"))
            self.assertLess(events.index("close_pipe"), events.index("terminate"))
            self.assertLess(events.index("join"), events.index("terminate"))
        else:
            self.assertEqual(events, ["send:stop", "close_pipe", "join"])

    def test_producer_exception_still_reconciles_and_drains_existing_queue(self) -> None:
        events: list[str] = []

        class Parent:
            def send(self, message: str) -> None:
                events.append(f"send:{message}")

            def close(self) -> None:
                events.append("close_pipe")

        class Process:
            alive = True
            exitcode = None

            def is_alive(self) -> bool:
                return self.alive

            def join(self, timeout: float | None = None) -> None:
                del timeout
                events.append("join")
                self.alive = False

            def terminate(self) -> None:
                events.append("terminate")
                self.alive = False

            def kill(self) -> None:
                events.append("kill")
                self.alive = False

        process = Process()
        parent = Parent()
        report = SimpleNamespace(candidates=1, queued=0, missing=(), failures=())
        fake_conn = object()
        reconciler = patch("scripts.run_daily.reconcile_missing_lot_images", return_value=report)
        drainer = patch("scripts.run_daily._wait_for_drain", return_value=None)
        with patch("scripts.run_daily.load_rules", return_value=object()), patch(
            "scripts.run_daily.process_lock", side_effect=lambda *_args: nullcontext()
        ), patch(
            "scripts.run_daily.connect", side_effect=lambda _path: nullcontext(fake_conn)
        ), patch(
            "scripts.run_daily.start_worker_process", return_value=(process, parent)
        ), patch(
            "scripts.run_daily._run_producer",
            side_effect=FetchError("source returned HTTP 503"),
        ), reconciler as reconcile_mock, drainer as drain_mock, patch(
            "scripts.run_daily.queue_state", return_value={"queued": 0}
        ), patch(
            "scripts.run_daily.count_lot_images", return_value={"permanent_error": 0}
        ):
            code = daily.run_daily(settings=self.settings, now=NOW)

        self.assertEqual(code, 1)
        reconcile_mock.assert_called_once()
        drain_mock.assert_called_once()
        self.assertIn("send:stop", events)

    def test_startup_passes_exact_isolated_settings_to_child(self) -> None:
        events: list[str] = []

        class Connection:
            def __init__(self, status: str | None = None) -> None:
                self.status = status
                self.closed = False

            def poll(self, _timeout: float) -> bool:
                return self.status is not None

            def recv(self) -> str:
                assert self.status is not None
                return self.status

            def send(self, message: str) -> None:
                events.append(f"send:{message}")

            def close(self) -> None:
                self.closed = True
                events.append("close")

        class Process:
            def __init__(self, target: object, args: tuple[object, ...], name: str) -> None:
                self.target = target
                self.args = args
                self.name = name
                self.alive = False
                self.exitcode = None

            def start(self) -> None:
                events.append("start")
                self.alive = True

            def is_alive(self) -> bool:
                return self.alive

            def join(self, timeout: float | None = None) -> None:
                del timeout
                self.alive = False

            def terminate(self) -> None:
                self.alive = False

            def kill(self) -> None:
                self.alive = False

        parent = Connection("ready")
        child = Connection()
        captured: dict[str, object] = {}

        class Context:
            def Pipe(self, duplex: bool = True) -> tuple[Connection, Connection]:
                self.duplex = duplex
                return parent, child

            def Process(self, *, target: object, args: tuple[object, ...], name: str) -> Process:
                process = Process(target, args, name)
                captured["process"] = process
                return process

        with patch("scripts.run_daily.multiprocessing.get_context", return_value=Context()):
            process, returned_parent = daily.start_worker_process(self.settings)

        made = captured["process"]
        self.assertIs(process, made)
        self.assertIs(returned_parent, parent)
        self.assertIs(getattr(made, "args")[0], self.settings)
        self.assertEqual(getattr(made, "args")[0].db_path, self.settings.db_path)
        self.assertIs(getattr(made, "args")[1], child)
        self.assertTrue(child.closed)
        daily._stop_worker(process, returned_parent)

    def test_failed_spawn_closes_both_pipes_without_orphan(self) -> None:
        events: list[str] = []

        class Connection:
            def close(self) -> None:
                events.append("close")

        class Process:
            exitcode = None

            def start(self) -> None:
                events.append("start")
                raise RuntimeError("simulated spawn cancellation")

            def is_alive(self) -> bool:
                return False

            def join(self, timeout: float | None = None) -> None:
                del timeout
                events.append("join")

            def terminate(self) -> None:
                events.append("terminate")

        class Context:
            def Pipe(self, duplex: bool = True) -> tuple[Connection, Connection]:
                del duplex
                return Connection(), Connection()

            def Process(self, **_kwargs: object) -> Process:
                return Process()

        with patch("scripts.run_daily.multiprocessing.get_context", return_value=Context()), self.assertRaises(
            RuntimeError
        ):
            daily.start_worker_process(self.settings)
        self.assertEqual(events, ["start", "close", "close"])

    def test_busy_startup_terminates_child_and_closes_both_pipes(self) -> None:
        events: list[str] = []

        class Connection:
            def __init__(self, status: str | None = None) -> None:
                self.status = status
                self.closed = False

            def poll(self, _timeout: float) -> bool:
                return self.status is not None

            def recv(self) -> str:
                assert self.status is not None
                return self.status

            def close(self) -> None:
                self.closed = True
                events.append("close")

        class Process:
            exitcode = 2

            def __init__(self) -> None:
                self.alive = False

            def start(self) -> None:
                events.append("start")
                self.alive = True

            def is_alive(self) -> bool:
                return self.alive

            def terminate(self) -> None:
                events.append("terminate")
                self.alive = False

            def join(self, timeout: float | None = None) -> None:
                del timeout
                events.append("join")

        parent = Connection("busy")
        child = Connection()
        process = Process()

        class Context:
            def Pipe(self, duplex: bool = True) -> tuple[Connection, Connection]:
                del duplex
                return parent, child

            def Process(self, **_kwargs: object) -> Process:
                return process

        with patch("scripts.run_daily.multiprocessing.get_context", return_value=Context()), self.assertRaises(
            ProcessLockBusy
        ):
            daily.start_worker_process(self.settings)
        self.assertGreaterEqual(events.count("close"), 2)
        self.assertIn("terminate", events)
        self.assertIn("join", events)
        self.assertLess(events.index("start"), events.index("terminate"))
        self.assertLess(events.index("terminate"), events.index("join"))

    def test_cli_rejects_actual_argv_instead_of_silently_ignoring_it(self) -> None:
        with patch("scripts.run_daily.run_daily", return_value=0) as runner:
            self.assertEqual(daily.main(["--unexpected"]), 2)
            runner.assert_not_called()
            self.assertEqual(daily.main([]), 0)
            runner.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
