"""Deterministic transports shared by daily-crawl regression tests."""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import socket
from typing import Any, Callable


@dataclass(frozen=True)
class UploadCall:
    source_url: str
    caption: str


class FakeTelegramTransport:
    """Return scripted sendPhoto results without opening a network socket."""

    def __init__(self, outcomes: list[dict[str, Any] | Exception]) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[UploadCall] = []

    def upload(self, source_url: str, caption: str, _settings: object) -> dict[str, Any]:
        self.calls.append(UploadCall(source_url, caption))
        if not self._outcomes:
            raise AssertionError("fake Telegram transport was called more times than scripted")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeClock:
    """A fixed clock/sleep recorder for worker tests that need polling later."""

    def __init__(self) -> None:
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def callback_transport(transport: FakeTelegramTransport) -> Callable[..., dict[str, Any]]:
    """Adapt a fake transport to the current upload function signature."""

    return transport.upload


@contextmanager
def block_network():
    """Fail loudly if a regression test accidentally opens a real socket."""

    original_socket = socket.socket
    original_create_connection = socket.create_connection

    def denied(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("offline regression attempted a network connection")

    socket.socket = denied  # type: ignore[assignment]
    socket.create_connection = denied  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original_socket
        socket.create_connection = original_create_connection


@contextmanager
def loopback_network_guard():
    """Allow only loopback TCP connects while preserving an active test server."""

    original_connect = socket.socket.connect
    original_create_connection = socket.create_connection

    def host_from_address(address: object) -> str | None:
        if isinstance(address, tuple) and address:
            return str(address[0])
        return None

    def guarded_connect(self: socket.socket, address: object) -> object:
        host = host_from_address(address)
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise AssertionError(f"integration attempted a non-loopback connection: {host!r}")
        return original_connect(self, address)  # type: ignore[arg-type]

    def guarded_create_connection(address: object, *args: object, **kwargs: object) -> socket.socket:
        host = host_from_address(address)
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise AssertionError(f"integration attempted a non-loopback connection: {host!r}")
        return original_create_connection(address, *args, **kwargs)  # type: ignore[arg-type]

    socket.socket.connect = guarded_connect  # type: ignore[assignment]
    socket.create_connection = guarded_create_connection  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = original_connect  # type: ignore[assignment]
        socket.create_connection = original_create_connection
