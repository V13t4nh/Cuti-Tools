"""Deterministic terminal and JSON output for the CUTI CLI."""

from __future__ import annotations

import json
from typing import Sequence


def emit(payload: dict[str, object], as_json: bool, lines: Sequence[str]) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print("\n".join(lines))
