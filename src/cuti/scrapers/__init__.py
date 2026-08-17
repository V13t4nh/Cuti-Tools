"""Source adapters. One module per source, each returning validated records."""

from __future__ import annotations

from . import catawiki, catawiki_api, deals

__all__ = ["catawiki", "catawiki_api", "deals"]
