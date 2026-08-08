"""Source adapters. One module per source, each returning validated records."""

from __future__ import annotations

from . import catawiki, deals

__all__ = ["catawiki", "deals"]
