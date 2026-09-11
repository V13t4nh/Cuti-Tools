"""Script to test Catawiki requests using curl-cffi TLS impersonation."""
import sys
import time
from curl_cffi import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

def test_endpoint(name: str, url: str, impersonate: str = "chrome124"):
    print(f"\n--- Testing: {name} ---")
    print(f"URL: {url}")
    t0 = time.perf_counter()
    try:
        session = requests.Session(impersonate=impersonate)
        headers = {
            "Accept": "application/json, text/plain, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = session.get(url, headers=headers, timeout=10)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        print(f"-> Status Code : {resp.status_code}")
        print(f"-> Latency     : {elapsed_ms:.1f} ms")
        print(f"-> Content Type: {resp.headers.get('content-type', 'N/A')}")
        print(f"-> Body Length : {len(resp.content):,} bytes")
        
        preview = resp.text[:300].replace("\n", " ")
        print(f"-> Body Preview: {preview}...")
        return resp
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        print(f"-> ERROR ({elapsed_ms:.1f} ms): {type(e).__name__}: {e}")
        return None

def main():
    print("=== KIỂM TRA GIẢ LẬP TLS (curl-cffi) VỚI CATAWIKI ===")
    
    # 1. Test search buyer API
    search_resp = test_endpoint("Buyer Search API", "https://www.catawiki.com/buyer/api/v1/search?q=omega&page=1")
    
    lot_id = None
    if search_resp and search_resp.status_code == 200:
        try:
            data = search_resp.json()
            lots = data.get("lots", []) or data.get("results", []) or []
            if lots and isinstance(lots, list):
                lot_id = str(lots[0].get("id"))
                print(f"[FOUND LOT ID]: {lot_id} - Title: {lots[0].get('title')}")
        except Exception as e:
            print(f"Failed to parse JSON: {e}")

    if not lot_id:
        lot_id = "106311347"

    # 2. Test live states API
    test_endpoint("Live States API", f"https://www.catawiki.com/buyer/api/v1/lots/live?ids={lot_id}")

    # 3. Test outcome / bidding block API
    test_endpoint("Bidding Block API", f"https://www.catawiki.com/buyer/api/v3/lots/{lot_id}/bidding_block?currency_code=EUR")

    # 4. Test Lot Details HTML Page
    test_endpoint("Lot Details HTML Page", f"https://www.catawiki.com/en/l/{lot_id}")

if __name__ == "__main__":
    main()
