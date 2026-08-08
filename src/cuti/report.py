"""Static HTML report: price distribution + liquidity ranking.

Rendered with the standard library only (inline SVG), so the report opens in
any browser and needs no runtime, CDN or charting dependency.
"""

from __future__ import annotations

import html
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

from .config import Settings
from .liquidity import LiquidityReport, compute_liquidity
from .models import Condition
from .pricing import percentile
from .storage import fetch_sold_lots_since

CHART_WIDTH = 720
CHART_HEIGHT = 260
CHART_PADDING = 36
DEFAULT_BINS = 12


@dataclass(frozen=True, slots=True)
class Histogram:
    edges: tuple[float, ...]
    counts: tuple[int, ...]


def build_histogram(values: Sequence[float], bins: int = DEFAULT_BINS) -> Histogram:
    """Equal-width histogram. A degenerate range collapses into one bin."""
    if bins < 1:
        raise ValueError(f"bins must be >= 1, got {bins}")
    if not values:
        return Histogram(edges=(), counts=())
    low, high = min(values), max(values)
    if low == high:
        return Histogram(edges=(low, high), counts=(len(values),))
    width = (high - low) / bins
    counts = [0] * bins
    for value in values:
        index = min(int((value - low) / width), bins - 1)
        counts[index] += 1
    edges = tuple(low + width * i for i in range(bins + 1))
    return Histogram(edges=edges, counts=tuple(counts))


def _svg_histogram(histogram: Histogram, title: str) -> str:
    if not histogram.counts:
        return f"<p class='empty'>{html.escape(title)}: no data in window</p>"
    max_count = max(histogram.counts)
    usable_width = CHART_WIDTH - 2 * CHART_PADDING
    usable_height = CHART_HEIGHT - 2 * CHART_PADDING
    bar_width = usable_width / len(histogram.counts)
    bars = []
    for index, count in enumerate(histogram.counts):
        height = 0.0 if max_count == 0 else usable_height * count / max_count
        x = CHART_PADDING + index * bar_width
        y = CHART_HEIGHT - CHART_PADDING - height
        bars.append(
            f"<rect x='{x:.1f}' y='{y:.1f}' width='{bar_width - 2:.1f}' "
            f"height='{height:.1f}' fill='#3f6ad8'><title>{count} lots</title></rect>"
        )
    axis = (
        f"<line x1='{CHART_PADDING}' y1='{CHART_HEIGHT - CHART_PADDING}' "
        f"x2='{CHART_WIDTH - CHART_PADDING}' y2='{CHART_HEIGHT - CHART_PADDING}' "
        "stroke='#888'/>"
    )
    labels = (
        f"<text x='{CHART_PADDING}' y='{CHART_HEIGHT - 12}' font-size='11'>"
        f"{histogram.edges[0]:,.0f} EUR</text>"
        f"<text x='{CHART_WIDTH - CHART_PADDING}' y='{CHART_HEIGHT - 12}' font-size='11' "
        f"text-anchor='end'>{histogram.edges[-1]:,.0f} EUR</text>"
    )
    return (
        f"<h3>{html.escape(title)}</h3>"
        f"<svg viewBox='0 0 {CHART_WIDTH} {CHART_HEIGHT}' role='img' "
        f"aria-label='{html.escape(title)}'>{axis}{''.join(bars)}{labels}</svg>"
    )


def _liquidity_table(report: LiquidityReport) -> str:
    if not report.brands:
        return "<p class='empty'>No brand has enough lots in the window.</p>"
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(item.brand)}</td>"
        f"<td>{html.escape(item.form.value)}</td>"
        f"<td>{item.lots}</td>"
        f"<td>{item.sold}</td>"
        f"<td>{item.sell_through:.0%}</td>"
        f"<td>{'-' if item.median_days_to_close is None else f'{item.median_days_to_close:.1f}'}</td>"
        f"<td>{item.heart_to_hammer:.0%}</td>"
        f"<td><b>{item.index:.3f}</b></td>"
        f"<td>{'-' if item.latest_qoq_change is None else f'{item.latest_qoq_change:+.0%}'}</td>"
        f"<td>{'STOP' if item.stop_buying else 'watch'}</td>"
        "</tr>"
        for item in report.brands
    )
    return (
        "<table><thead><tr><th>Brand</th><th>Form</th><th>Lots</th><th>Sold</th>"
        "<th>Sell-through</th><th>Median days</th><th>Hot\u2192sold</th>"
        "<th>Liquidity index</th><th>QoQ</th><th>Signal</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _stats_block(prices: Sequence[float]) -> str:
    if not prices:
        return "<p class='empty'>No sold lots in window.</p>"
    return (
        "<ul class='stats'>"
        f"<li>Sample: <b>{len(prices)}</b> sold lots</li>"
        f"<li>p25: <b>{percentile(prices, 0.25):,.0f} EUR</b></li>"
        f"<li>median: <b>{percentile(prices, 0.50):,.0f} EUR</b></li>"
        f"<li>p75: <b>{percentile(prices, 0.75):,.0f} EUR</b></li>"
        "</ul>"
    )


STYLE = """
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 32px; color: #1c1c1c; }
h1 { font-size: 22px; } h2 { font-size: 17px; margin-top: 28px; }
table { border-collapse: collapse; margin-top: 8px; font-size: 14px; }
th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; }
th { background: #f4f6fb; }
.stats { list-style: none; padding: 0; display: flex; gap: 20px; font-size: 14px; }
.empty { color: #777; font-style: italic; }
svg { max-width: 100%; height: auto; }
footer { margin-top: 32px; color: #777; font-size: 12px; }
"""


def render_report(conn: sqlite3.Connection, settings: Settings, today: date) -> str:
    """Build the full HTML document."""
    since = date.fromordinal(max(1, today.toordinal() - settings.comparable_window_days))
    sections = []
    for condition in Condition:
        lots = [
            lot
            for lot in fetch_sold_lots_since(conn, condition, since)
            if lot.ended_at <= today and lot.hammer_eur is not None
        ]
        prices = [float(lot.hammer_eur) for lot in lots if lot.hammer_eur is not None]
        sections.append(
            "<section>"
            + _svg_histogram(
                build_histogram(prices), f"Hammer price distribution \u2014 {condition.value}"
            )
            + _stats_block(prices)
            + "</section>"
        )
    liquidity = compute_liquidity(conn, settings, today)
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>CUTI-Tools report {today.isoformat()}</title><style>{STYLE}</style></head><body>"
        f"<h1>CUTI-Tools \u2014 market report</h1>"
        f"<p>Window: {since.isoformat()} \u2192 {today.isoformat()} "
        f"({settings.comparable_window_days} days)</p>"
        "<h2>Price distribution by condition</h2>"
        + "".join(sections)
        + "<h2>Liquidity index by brand</h2>"
        + _liquidity_table(liquidity)
        + "<footer>Generated locally by CUTI-Tools.</footer>"
        "</body></html>"
    )


def write_report(conn: sqlite3.Connection, settings: Settings, today: date) -> Path:
    path = settings.report_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(conn, settings, today), encoding="utf-8")
    return path
