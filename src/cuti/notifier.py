"""Alert delivery.

Two interchangeable implementations selected by ``CUTI_NOTIFIER``:
``file`` (JSONL on disk, used by tests and local runs) and ``telegram``.
Both raise on failure; an undelivered alert is never reported as delivered.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from .config import Settings
from .errors import NotifierError
from .fetch import post_json


class Notifier(Protocol):
    """Delivers one alert payload."""

    def send(self, payload: dict[str, Any]) -> None: ...


def format_message(payload: dict[str, Any]) -> str:
    """Human-readable alert text shared by every notifier (DRY)."""
    return (
        f"[{payload['verdict'].upper()}] {payload['title']}\n"
        f"Ask: {payload['ask_vnd']:,} VND | Net p25: {payload['net_p25_eur']} EUR "
        f"(threshold {payload['threshold_eur']} EUR)\n"
        f"Sold/attempts: {payload['sample_size']}/{payload['attempt_count']} | "
        f"Model: {payload['model_key']} ({payload['condition']}, {payload['form']})\n"
        f"{payload['url']}"
    )


class FileNotifier:
    """Appends one JSON object per alert. Deterministic and inspectable."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def send(self, payload: dict[str, Any]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {**payload, "message": format_message(payload)},
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )
        except OSError as exc:
            raise NotifierError(f"cannot write alert to {self._path}: {exc}") from exc


class TelegramNotifier:
    """Posts to the Telegram Bot API. The API base is configurable."""

    def __init__(
        self,
        api_base: str,
        bot_token: str,
        chat_id: str,
        timeout_seconds: float,
        response_max_bytes: int,
    ) -> None:
        self._url = f"{api_base}/bot{bot_token}/sendMessage"
        self._chat_id = chat_id
        self._timeout = timeout_seconds
        self._response_max_bytes = response_max_bytes

    def send(self, payload: dict[str, Any]) -> None:
        response = post_json(
            self._url,
            {
                "chat_id": self._chat_id,
                "text": format_message(payload),
                "disable_web_page_preview": False,
            },
            self._timeout,
            max_bytes=self._response_max_bytes,
        )
        if not isinstance(response, dict) or response.get("ok") is not True:
            raise NotifierError(f"telegram rejected the alert: {response!r}")


def build_notifier(settings: Settings) -> Notifier:
    """Factory driven by configuration; unknown kinds are impossible here
    because :func:`load_settings` already validated the value."""
    if settings.notifier == "file":
        return FileNotifier(settings.notifier_file_path)
    return TelegramNotifier(
        api_base=settings.telegram_api_base,
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        timeout_seconds=settings.http_timeout_seconds,
        response_max_bytes=settings.response_max_bytes,
    )
