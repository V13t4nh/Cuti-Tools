"""Windows-spawn integration checks for the isolated daily parent and worker."""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import scripts.run_daily as daily
from cuti.scrapers import catawiki_api
from cuti.storage import connect, fetch_lot_image, upsert_lot_image, upsert_lots
from cuti.storage import count_lot_images
from daily_crawl_harness import loopback_network_guard
from process_lock import process_lock
from support import make_lot, settings_for


NOW = datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc)
RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "rules.json"


class _FrozenCrawlerDateTime(datetime):
    @classmethod
    def now(cls, tz: object = None) -> datetime:
        del tz
        return NOW


class _LoopbackTelegramHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.client_address[0] != "127.0.0.1":
            self.send_error(403, "loopback only")
            return
        size = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(size)
        server = self.server
        server.calls.append((self.path, json.loads(body.decode("utf-8"))))
        response = {
            "ok": True,
            "result": {
                "message_id": 9101,
                "photo": [{"file_id": "isolated-file", "file_unique_id": "isolated-unique"}],
            },
        }
        encoded = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args: object) -> None:
        return


class _LoopbackTelegramServer(ThreadingHTTPServer):
    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _LoopbackTelegramHandler)
        self.calls: list[tuple[str, dict[str, object]]] = []


class _DailySliceFakeCatawikiApi:
    """Replay one source search, live-state batch, and exact cover lookup."""

    def __init__(self) -> None:
        self.requests_made = 0
        self.search_calls: list[tuple[str, int]] = []
        self.live_state_calls: list[tuple[str, ...]] = []
        self.cover_calls: list[tuple[str, ...]] = []

    def search(self, query: str, page: int) -> catawiki_api.SearchPage:
        self.requests_made += 1
        self.search_calls.append((query, page))
        if page != 1:
            return catawiki_api.SearchPage(total=1, lots=())
        return catawiki_api.SearchPage(
            total=1,
            lots=(
                catawiki_api.LotRef(
                    lot_id="newlot",
                    title="New source lot",
                    subtitle="Men",
                    url="https://www.catawiki.com/en/l/900001-new-source-lot",
                    image_url="https://assets.invalid/newlot.jpg",
                ),
            ),
        )

    def live_states(self, lot_ids: tuple[str, ...]) -> dict[str, catawiki_api.LiveState]:
        self.requests_made += 1
        ids = tuple(lot_ids)
        self.live_state_calls.append(ids)
        return {
            lot_id: catawiki_api.LiveState(
                lot_id=lot_id,
                closed=False,
                favorite_count=1,
                opened_at=NOW.date(),
                ended_at=NOW.date().replace(day=28),
                current_bid_eur=None,
            )
            for lot_id in ids
        }

    def covers(self, lot_ids: tuple[str, ...]) -> dict[str, str | None]:
        self.requests_made += 1
        ids = tuple(lot_ids)
        self.cover_calls.append(ids)
        return {lot_id: "https://assets.invalid/oldmissing.jpg" for lot_id in ids}


class DailyProcessIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="cuti-daily-process-"))
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)
        self.server = _LoopbackTelegramServer()
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.addCleanup(self._stop_server)
        host, port = self.server.server_address
        self.settings = settings_for(
            self.temp_dir,
            CUTI_DB_PATH=str(self.temp_dir / "isolated.db"),
            CUTI_RULES_PATH=str(RULES_PATH),
            CUTI_NOTIFIER="file",
            CUTI_TELEGRAM_API_BASE=f"http://{host}:{port}",
            CUTI_TELEGRAM_BOT_TOKEN="fake-bot-token",
            CUTI_TELEGRAM_CHAT_ID="-1000000000000",
            CUTI_TELEGRAM_CHANNEL_ID="",
            CUTI_TELEGRAM_UPLOAD_PAUSE_SECONDS="0",
            CUTI_TELEGRAM_UPLOAD_LEASE_SECONDS="5",
        )
        with connect(self.settings.db_path):
            pass

    def _stop_server(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=5)

    def _seed_queued_cover(self, lot_id: str = "isolated-lot") -> None:
        with connect(self.settings.db_path) as conn:
            upsert_lots(conn, [make_lot(lot_id)], NOW)
            upsert_lot_image(
                conn,
                lot_id=lot_id,
                idx=0,
                source_url=f"https://assets.invalid/{lot_id}.jpg",
            )

    def _seed_full_daily_slice_state(self) -> None:
        old_time = datetime(2026, 8, 20, 4, 0, tzinfo=timezone.utc)
        ready_time = datetime(2026, 8, 21, 4, 0, tzinfo=timezone.utc)
        with connect(self.settings.db_path) as conn:
            upsert_lots(
                conn,
                [make_lot("oldmissing"), make_lot("ready-existing")],
                old_time,
            )
            upsert_lot_image(
                conn,
                lot_id="ready-existing",
                idx=0,
                source_url="https://assets.invalid/ready-existing.jpg",
                telegram_file_id="preexisting-file",
                telegram_file_path=None,
                telegram_message_id=7001,
                uploaded_at=ready_time,
            )

    def _producer_ok(self, *_args: object, **_kwargs: object) -> tuple[bool, list[str]]:
        return True, []

    def _bounded_sleep(self, seconds: float) -> None:
        time.sleep(min(seconds, 0.05))

    def _no_reconcile(self, *_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(candidates=0, queued=0, missing=(), failures=())

    def test_run_daily_spawn_drains_temp_queue_and_ready_is_idempotent(self) -> None:
        self._seed_queued_cover()
        with patch("scripts.run_daily.load_rules", return_value=object()), patch(
            "scripts.run_daily._run_producer", side_effect=self._producer_ok
        ), patch(
            "scripts.run_daily.reconcile_missing_lot_images", side_effect=self._no_reconcile
        ), loopback_network_guard():
            first = daily.run_daily(settings=self.settings, now=NOW, sleep=lambda _seconds: None)
            second = daily.run_daily(settings=self.settings, now=NOW, sleep=lambda _seconds: None)

        self.assertEqual(first, 0)
        self.assertEqual(second, 0)
        self.assertEqual(len(self.server.calls), 1)
        path, payload = self.server.calls[0]
        self.assertEqual(path, "/botfake-bot-token/sendPhoto")
        self.assertEqual(payload["chat_id"], "-1000000000000")
        self.assertEqual(payload["photo"], "https://assets.invalid/isolated-lot.jpg")
        with connect(self.settings.db_path) as conn:
            image = fetch_lot_image(conn, "isolated-lot")
            self.assertIsNotNone(image)
            assert image is not None
            self.assertEqual(image["state"], "ready")
            self.assertEqual(image["telegram_file_id"], "isolated-file")
            self.assertEqual(count_lot_images(conn)["ready"], 1)

    def test_actual_standalone_uploader_lock_is_rejected(self) -> None:
        lock_path = self.settings.db_path.with_suffix(self.settings.db_path.suffix + ".image.lock")
        with process_lock(lock_path, "test owns image worker lock"), patch(
            "scripts.run_daily.load_rules", return_value=object()
        ), loopback_network_guard():
            result = daily.run_daily(settings=self.settings, now=NOW, sleep=lambda _seconds: None)

        self.assertEqual(result, 2)
        self.assertEqual(self.server.calls, [])

    def test_actual_worker_exits_and_releases_lock_when_parent_pipe_closes(self) -> None:
        worker = None
        parent = None
        lock_path = self.settings.db_path.with_suffix(self.settings.db_path.suffix + ".image.lock")
        with loopback_network_guard():
            try:
                worker, parent = daily.start_worker_process(self.settings)
                parent.close()
                worker.join(timeout=10)
                self.assertFalse(worker.is_alive())
                self.assertEqual(worker.exitcode, 3)
            finally:
                if parent is not None:
                    try:
                        parent.close()
                    except (OSError, EOFError):
                        pass
                if worker is not None and worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=5)
        with process_lock(lock_path, "lock should be released after parent death"):
            pass

    def test_full_daily_slice_uses_real_producer_and_reconciler(self) -> None:
        self._seed_full_daily_slice_state()
        fake_api = _DailySliceFakeCatawikiApi()
        # The producer and reconciler are intentionally unpatched: this is the
        # full parent workflow with only the source API substituted.
        with patch("run_scheduled_crawl.datetime", _FrozenCrawlerDateTime), loopback_network_guard():
                self.assertEqual(
                    daily._run_producer.__globals__["datetime"].now(timezone.utc),
                    NOW,
                )
                first = daily.run_daily(
                    settings=self.settings,
                    now=NOW,
                    api=fake_api,
                    sleep=self._bounded_sleep,
                )
                second = daily.run_daily(
                    settings=self.settings,
                    now=NOW,
                    api=fake_api,
                    sleep=self._bounded_sleep,
                )

        self.assertEqual(first, 0)
        self.assertEqual(second, 0)
        self.assertEqual(fake_api.search_calls, [("watch", 1), ("watch", 2)])
        self.assertEqual(fake_api.cover_calls, [("oldmissing",)])
        self.assertEqual(len(self.server.calls), 2)
        self.assertEqual(
            {payload["photo"] for _path, payload in self.server.calls},
            {"https://assets.invalid/newlot.jpg", "https://assets.invalid/oldmissing.jpg"},
        )
        with connect(self.settings.db_path) as conn:
            oldmissing = fetch_lot_image(conn, "oldmissing")
            newlot = fetch_lot_image(conn, "newlot")
            ready_existing = fetch_lot_image(conn, "ready-existing")
            self.assertEqual(oldmissing["state"], "ready")
            self.assertEqual(newlot["state"], "ready")
            self.assertEqual(ready_existing["state"], "ready")
            self.assertEqual(ready_existing["telegram_file_id"], "preexisting-file")
            self.assertEqual(ready_existing["telegram_message_id"], 7001)
            self.assertEqual(count_lot_images(conn)["ready"], 3)


if __name__ == "__main__":
    unittest.main()
