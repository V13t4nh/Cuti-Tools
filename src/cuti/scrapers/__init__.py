"""Source adapters. One module per source, each returning validated records."""

from __future__ import annotations

from . import catawiki, catawiki_api, catawiki_lot_page, deals

__all__ = ["catawiki", "catawiki_api", "catawiki_lot_page", "deals"]
