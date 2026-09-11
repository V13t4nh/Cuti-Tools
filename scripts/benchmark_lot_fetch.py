"""Benchmark script to test speed and anti-bot safety between different approaches:
Approach 1: Direct curl/HTML fetch + regex parse (simulating Ctrl+U)
Approach 2: Check for potential JSON / GraphQL endpoints
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from cuti.fetch import DEFAULT_HEADERS, fetch_text, fetch_json

SAMPLE_LOT_URL = "https://www.catawiki.com/en/l/106311347-rado-jade-no-reserve-price-5509-women-1980-1989"
SAMPLE_LOT_ID = "106311347"

def test_html_fetch_and_parse():
    print("--- TEST 1: FETCH HTML TRỰC TIẾP (Ctrl+U / Curl style) ---")
    t0 = time.perf_counter()
    html = fetch_text(SAMPLE_LOT_URL, timeout_seconds=15.0)
    fetch_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    # Trích xuất toàn bộ ảnh gốc
    matches = set(re.findall(r'https://assets\.catawiki\.nl/assets/[^"\'\s<>]+?\.(?:jpg|jpeg|png|webp)', html, re.IGNORECASE))
    high_res = set()
    for u in matches:
        if "/categories/" not in u and "/buyer/" not in u:
            high_res.add(re.sub(r'/thumb\d*_', '/', u))
    parse_ms = (time.perf_counter() - t1) * 1000

    print(f"-> Thời gian tải HTML sàn : {fetch_ms:.1f} ms")
    print(f"-> Dung lượng HTML        : {len(html):,} ký tự (~{len(html)/1024:.1f} KB)")
    print(f"-> Thời gian bóc tách     : {parse_ms:.2f} ms")
    print(f"-> Số ảnh thu hoạch       : {len(high_res)} ảnh nét gốc")
    return fetch_ms, len(high_res)

def test_graphql_or_json_api():
    print("\n--- TEST 2: THỬ NGHIỆM ENDPOINT JSON / GRAPHQL (Siêu nhẹ nếu có) ---")
    # Kiểm tra GraphQL của Catawiki
    graphql_url = "https://www.catawiki.com/graphql"
    query = """
    query GetLotImages($id: ID!) {
      lot(id: $id) {
        id
        photos {
          url
          original
        }
      }
    }
    """
    payload = json.dumps({"query": query, "variables": {"id": SAMPLE_LOT_ID}}).encode("utf-8")
    headers = dict(DEFAULT_HEADERS)
    headers["Content-Type"] = "application/json"
    req = urllib.request.Request(graphql_url, data=payload, headers=headers, method="POST")

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed_ms = (time.perf_counter() - t0) * 1000
            print(f"-> GraphQL phản hồi: {resp.status} trong {elapsed_ms:.1f} ms")
            print(f"   Data: {str(data)[:200]}")
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        print(f"-> GraphQL không khả dụng hoặc bị chặn: {e} ({elapsed_ms:.1f} ms)")

def main():
    print("=== ĐO ĐẠC HIỆU NĂNG & ĐỘ AN TOÀN TRÍCH XUẤT ẢNH ===")
    test_html_fetch_and_parse()
    test_graphql_or_json_api()

if __name__ == "__main__":
    main()
