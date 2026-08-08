"""Deterministic sample-data generator.

Produces the fixtures the MVP runs against out of the box:

* ``data/sample/catawiki/page-N.html`` — paginated auction listings
* ``data/sample/deals/deals.json``     — Vietnamese marketplace feed

A fixed seed keeps every run byte-identical, so tests and demos are stable.
"""

from __future__ import annotations

import argparse
import html
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20260807
REFERENCE_DAY = date(2026, 8, 1)
LOTS_PER_PAGE = 48
PAGES = 8

MODELS: tuple[tuple[str, str, int, str], ...] = (
    # (brand, model text, typical hammer price in EUR, case form)
    ("Omega", "Seamaster Diver 300M 210.30.42", 3200, "round"),
    ("Omega", "Speedmaster Professional 311.30.42", 4200, "round"),
    ("Rolex", "Datejust 126234", 8200, "round"),
    ("Rolex", "Submariner 124060", 11500, "round"),
    ("Seiko", "Prospex SPB143", 700, "round"),
    ("Seiko", "Presage SRPB41", 380, "round"),
    ("Tudor", "Black Bay 58 79030", 3100, "round"),
    ("Longines", "Spirit Zulu L3.812", 1900, "round"),
    ("Hamilton", "Khaki Field H70455", 520, "round"),
    ("Oris", "Aquis 733", 1400, "round"),
    ("Tissot", "PRX 137", 430, "tonneau"),
    ("Citizen", "Tsuyosa NJ0150", 300, "round"),
)

CONDITION_SUFFIX: tuple[tuple[str, str, float], ...] = (
    ("watch only", "naked", 1.00),
    ("with box", "box", 1.05),
    ("with papers", "papers", 1.08),
    ("full set", "fullset", 1.15),
)


def _lot_html(
    lot_id: str,
    title: str,
    hearts: int,
    sold: bool,
    hammer: int | None,
    opened_at: date,
    ended_at: date,
    condition: str,
    form: str,
) -> str:
    hammer_attr = f' data-hammer-eur="{hammer}"' if hammer is not None else ""
    return (
        "    <div class=\"lot-card\""
        f' data-lot-id="{lot_id}"'
        f' data-title="{html.escape(title, quote=True)}"'
        f' data-condition="{condition}"'
        f' data-form="{form}"'
        f' data-hearts="{hearts}"'
        f' data-sold="{str(sold).lower()}"'
        f"{hammer_attr}"
        f' data-opened-at="{opened_at.isoformat()}"'
        f' data-ended-at="{ended_at.isoformat()}"'
        f' data-url="lots/{lot_id}.html"></div>'
    )


def _page_html(page_number: int, lots_html: list[str], has_next: bool) -> str:
    next_link = (
        f'    <a class="pagination-next" href="page-{page_number + 1}.html">Next</a>\n'
        if has_next
        else ""
    )
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head><meta charset=\"utf-8\">"
        f"<title>Closed watch auctions \u2014 page {page_number}</title></head>\n"
        "<body>\n  <main class=\"results\">\n"
        + "\n".join(lots_html)
        + "\n"
        + next_link
        + "  </main>\n</body>\n</html>\n"
    )


def generate_lots(rng: random.Random, base_dir: Path) -> int:
    out_dir = base_dir / "data" / "sample" / "catawiki"
    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    counter = 0

    for page in range(1, PAGES + 1):
        lots_html: list[str] = []
        for _ in range(LOTS_PER_PAGE):
            counter += 1
            brand, model, base_price, form = MODELS[counter % len(MODELS)]
            suffix, condition, multiplier = CONDITION_SUFFIX[
                (counter // len(MODELS)) % len(CONDITION_SUFFIX)
            ]
            title = f"{brand} {model} - {suffix}"
            hearts = rng.randint(0, 180)
            sold = rng.random() < 0.78
            noise = rng.uniform(0.82, 1.24)
            hammer = int(base_price * multiplier * noise) if sold else None
            ended_at = REFERENCE_DAY - timedelta(days=rng.randint(1, 690))
            opened_at = ended_at - timedelta(days=rng.randint(5, 45))
            lots_html.append(
                _lot_html(
                    lot_id=f"cw-{counter:05d}",
                    title=title,
                    hearts=hearts,
                    sold=sold,
                    hammer=hammer,
                    opened_at=opened_at,
                    ended_at=ended_at,
                    condition=condition,
                    form=form,
                )
            )
            total += 1
        (out_dir / f"page-{page}.html").write_text(
            _page_html(page, lots_html, has_next=page < PAGES), encoding="utf-8"
        )
    return total


def generate_deals(base_dir: Path) -> int:
    """A hand-written feed covering green / yellow / red / thin-data cases."""
    out_dir = base_dir / "data" / "sample" / "deals"
    out_dir.mkdir(parents=True, exist_ok=True)
    feed = [
        {
            "source": "fb-group-dongho",
            "title": "Rolex Submariner 124060 full set",
            "ask_vnd": 150_000_000,
            "url": "https://example.invalid/deals/1",
            "seen_at": "2026-08-01",
            "condition": "fullset",
            "form": "round",
        },
        {
            "source": "fb-group-dongho",
            "title": "Omega Seamaster Diver 300M 210.30.42 with box",
            "ask_vnd": 70_000_000,
            "url": "https://example.invalid/deals/2",
            "seen_at": "2026-08-01",
            "condition": "box",
            "form": "round",
        },
        {
            "source": "cho-dong-ho-cu",
            "title": "Seiko Prospex SPB143 watch only",
            "ask_vnd": 21_000_000,
            "url": "https://example.invalid/deals/3",
            "seen_at": "2026-07-31",
            "condition": "naked",
            "form": "round",
        },
        {
            "source": "cho-dong-ho-cu",
            "title": "Tudor Black Bay 58 79030 with papers",
            "ask_vnd": 62_000_000,
            "url": "https://example.invalid/deals/4",
            "seen_at": "2026-07-30",
            "condition": "papers",
            "form": "round",
        },
        {
            "source": "fb-group-dongho",
            "title": "Omega Constellation 131.12.41 full set",
            "ask_vnd": 95_000_000,
            "url": "https://example.invalid/deals/5",
            "seen_at": "2026-07-29",
            "condition": "fullset",
            "form": "round",
        },
        {
            # exact duplicate of deal #2: exercises the dedupe path
            "source": "fb-group-dongho",
            "title": "Omega Seamaster Diver 300M 210.30.42 with box",
            "ask_vnd": 70_000_000,
            "url": "https://example.invalid/deals/2",
            "seen_at": "2026-08-02",
            "condition": "box",
            "form": "round",
        },
    ]
    (out_dir / "deals.json").write_text(
        json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return len(feed)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic sample data")
    parser.add_argument(
        "--home", type=Path, default=Path(__file__).resolve().parents[1], help="project root"
    )
    args = parser.parse_args()
    rng = random.Random(SEED)
    lots = generate_lots(rng, args.home)
    deals = generate_deals(args.home)
    print(f"generated {lots} lots across {PAGES} pages and {deals} deals under {args.home}/data/sample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
