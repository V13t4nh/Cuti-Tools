"""Lightweight REST API server bridging CUTI core logic to Next.js frontend."""

from __future__ import annotations

import json
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
import sys
from urllib.parse import parse_qs, urlparse

from .comparables import find_comparables
from .config import load_settings
from .errors import CutiError
from .evaluation_chart import evaluate_deal_with_chart
from .liquidity import compute_liquidity
from .models import Condition, WatchForm
from .normalize import load_rules
from .storage import connect, count_rows, fetch_lots_for_liquidity


class CutiApiHandler(BaseHTTPRequestHandler):
    """HTTP request handler for CUTI-Tools API."""

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, status: int, data: dict | list) -> None:
        payload = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_cors_headers()
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        settings = load_settings()
        today = date.today()

        with connect(settings.db_path) as conn:
            if path == "/api/status":
                lots_count = count_rows(conn, "lots")
                queue_count = count_rows(conn, "live_watch")
                self._send_json(200, {
                    "lots_count": lots_count,
                    "live_watch_count": queue_count,
                    "eur_vnd_rate": settings.eur_vnd_rate,
                    "match_threshold": settings.match_threshold,
                    "min_comparables": settings.min_comparables,
                })
            elif path == "/api/liquidity":
                report = compute_liquidity(conn, settings, today)
                brands = [
                    {
                        "brand": b.brand,
                        "form": b.form.value,
                        "lots": b.lots,
                        "sold": b.sold,
                        "sell_through": b.sell_through,
                        "median_days_to_close": b.median_days_to_close,
                        "speed": b.speed,
                        "heart_to_hammer": b.heart_to_hammer,
                        "index": b.index,
                        "latest_qoq_change": b.latest_qoq_change,
                        "stop_buying": b.stop_buying,
                        "status": b.status or "stable",
                    }
                    for b in report.brands
                ]
                self._send_json(200, {"brands": brands})
            elif path == "/api/live-lots":
                cursor = conn.execute(
                    "SELECT lot_id, title, bidding_end_at, url FROM live_watch ORDER BY bidding_end_at ASC LIMIT 100"
                )
                rows = [dict(r) for r in cursor.fetchall()]
                self._send_json(200, {"lots": rows})
            else:
                self._send_json(404, {"error": f"Endpoint not found: {path}"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path != "/api/evaluate":
            self._send_json(404, {"error": f"Endpoint not found: {path}"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)
        try:
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            self._send_json(400, {"error": "Invalid JSON body"})
            return

        query = body.get("query", "").strip()
        cost = float(body.get("cost", 0))
        currency = body.get("currency", "vnd").lower()
        cond_str = body.get("condition", "fullset").lower()
        form_str = body.get("form", "round").lower()

        if not query or cost <= 0:
            self._send_json(400, {"error": "query and positive cost are required"})
            return

        settings = load_settings()
        rules = load_rules(settings.rules_path)
        today = date.today()
        cond_obj = Condition.parse(cond_str)

        try:
            with connect(settings.db_path) as conn:
                eval_res = evaluate_deal_with_chart(
                    conn, rules, settings,
                    query=query, cost=cost, currency=currency,
                    condition=cond_obj, today=today,
                )
                raw_matches = find_comparables(
                    conn, title=query, condition=cond_obj,
                    rules=rules, settings=settings, today=today,
                )

                comparables = [
                    {
                        "lot_id": m.lot.lot_id,
                        "title": m.lot.title,
                        "brand": m.lot.brand,
                        "hammer_eur": m.lot.hammer_eur,
                        "hammer_vnd": int(round(m.lot.hammer_eur * settings.eur_vnd_rate)) if m.lot.hammer_eur else None,
                        "hearts": m.lot.hearts,
                        "bids_count": m.lot.bids_count,
                        "ended_at": str(m.lot.ended_at),
                        "score": round(m.score, 3),
                        "url": m.lot.url,
                    }
                    for m in raw_matches
                ]

                d = eval_res.decision
                c = eval_res.chart
                self._send_json(200, {
                    "decision": {
                        "verdict": d.verdict.value,
                        "max_buy_cost_vnd": d.max_buy_cost_vnd,
                        "sample_size": d.sample_size,
                        "sell_through_rate": d.sell_through_rate,
                        "median_days_to_close": d.median_days_to_close,
                        "heart_to_hammer_rate": d.heart_to_hammer_rate,
                        "net_p25_eur": d.net_p25_eur,
                        "net_median_eur": d.net_median_eur,
                        "net_p75_eur": d.net_p75_eur,
                        "reason": d.reason,
                        "threshold_eur": d.threshold_eur,
                    },
                    "chart": {
                        "hammer_prices_eur": list(c.hammer_prices_eur),
                        "input_hammer_eur": c.input_hammer_eur,
                        "cycle_position": c.cycle_position,
                        "heart_acceleration_rate": c.heart_acceleration_rate,
                    },
                    "comparables": comparables,
                    "eur_vnd_rate": settings.eur_vnd_rate,
                })
        except CutiError as exc:
            self._send_json(422, {"error": str(exc)})


def run_server(port: int = 8000, host: str = "0.0.0.0") -> None:
    """Start the CUTI REST API server."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, CutiApiHandler)
    print(f"[CUTI API] Server running on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[CUTI API] Server shutting down...")
        httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port=port)
