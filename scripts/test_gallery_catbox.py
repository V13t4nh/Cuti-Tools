"""Experimental script to test extracting all images from a Catawiki lot
and syncing them via Catbox remote URL upload.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from cuti.fetch import DEFAULT_HEADERS, fetch_text

CATBOX_API = "https://catbox.moe/user/api.php"

def get_sample_lot_from_db(db_path: str = "var/auctions.db") -> tuple[str, str, str]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Find a lot that has a valid URL
    cur.execute("SELECT lot_id, title, url FROM lots ORDER BY RANDOM() LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        raise RuntimeError("No lots found in db")
    return str(row[0]), str(row[1]), str(row[2])

def extract_all_images(html: str) -> list[str]:
    """Extract all distinct high-resolution image URLs from Catawiki lot HTML."""
    raw_matches = set(re.findall(r'https://assets\.catawiki\.nl/assets/[^"\'\s<>]+?\.(?:jpg|jpeg|png|webp)', html, re.IGNORECASE))
    
    # Standardize and deduplicate:
    # Notice Catawiki URLs have thumb versions:
    # https://assets.catawiki.nl/assets/2026/8/1/e/5/3/thumb5_e5306880-...jpg
    # High-res is:
    # https://assets.catawiki.nl/assets/2026/8/1/e/5/3/e5306880-...jpg
    high_res_set = set()
    for u in raw_matches:
        # Exclude category banners or non-lot assets (like categories/333-...)
        if "/categories/" in u or "/buyer/" in u:
            continue
        # Strip thumb prefixes
        normalized = re.sub(r'/thumb\d*_', '/', u)
        high_res_set.add(normalized)

    # Filter out any that don't match typical lot image patterns (UUID-like or timestamp structure)
    cleaned = [u for u in high_res_set if any(char.isdigit() for char in u.split('/')[-1])]
    return sorted(cleaned)

def upload_url_to_catbox(image_url: str, timeout: float = 25.0) -> str:
    """Send urlupload request to Catbox."""
    payload = urllib.parse.urlencode({
        "reqtype": "urlupload",
        "url": image_url,
    }).encode("utf-8")
    req = urllib.request.Request(
        CATBOX_API,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": DEFAULT_HEADERS["User-Agent"],
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8").strip()

def verify_remote_url(target_url: str) -> tuple[int, str, int]:
    """Verify that the target URL is accessible and returns valid image data."""
    req = urllib.request.Request(target_url, headers=DEFAULT_HEADERS)
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        status = resp.status
        content_type = resp.headers.get("Content-Type", "")
        body = resp.read()
        return status, content_type, len(body)

def main():
    print("=== BẮT ĐẦU TEST TOÀN DIỆN TRICK CATBOX VỚI 1 LÔ NGẪU NHIÊN ===")
    try:
        lot_id, title, url = get_sample_lot_from_db()
    except Exception as e:
        print(f"[!] Lỗi truy vấn DB: {e}")
        return

    print(f"-> Đã chọn lô ngẫu nhiên: {lot_id}")
    print(f"   Tiêu đề: {title[:75]}...")
    print(f"   URL sàn: {url}")

    try:
        html = fetch_text(url, timeout_seconds=15.0)
    except Exception as e:
        print(f"[!] Không thể tải trang Catawiki: {e}")
        return

    image_urls = extract_all_images(html)
    print(f"\n-> Bóc tách thành công: {len(image_urls)} ảnh độ phân giải cao của lô này!")
    for idx, u in enumerate(image_urls):
        print(f"   [{idx+1:02d}] {u}")

    if not image_urls:
        print("[!] Không tìm thấy ảnh nào. Kết thúc test.")
        return

    # Lấy 3 ảnh đầu tiên để test upload
    test_subset = image_urls[:3]
    print(f"\n-> Bắt đầu test Remote URL Upload lên Catbox với {len(test_subset)} ảnh đầu tiên...")

    success_count = 0
    results = []
    for idx, orig_url in enumerate(test_subset):
        print(f"\n[Ảnh {idx+1}/{len(test_subset)}] Gửi lệnh cho Catbox kéo:")
        print(f"   Link gốc: {orig_url}")
        t0 = time.perf_counter()
        try:
            catbox_url = upload_url_to_catbox(orig_url)
            elapsed = time.perf_counter() - t0
            print(f"   -> Phản hồi từ Catbox: {catbox_url} (mất {elapsed:.2f}s)")
            
            if catbox_url.startswith("http://") or catbox_url.startswith("https://"):
                status, ctype, size = verify_remote_url(catbox_url)
                print(f"   -> Kiểm chứng tải ảnh: HTTP {status} | Content-Type: {ctype} | Kích thước: {size:,} bytes")
                if status == 200 and "image" in ctype and size > 5000:
                    print(f"   -> [THÀNH CÔNG 100%] File nhị phân đã lưu trên Catbox, mở thẻ <img> xem được ngay!")
                    success_count += 1
                    results.append((orig_url, catbox_url, size))
                else:
                    print(f"   -> [CẢNH BÁO] Phản hồi không phải file ảnh hợp lệ.")
            else:
                print(f"   -> [THẤT BẠI] Catbox từ chối hoặc lỗi: {catbox_url}")
        except Exception as err:
            elapsed = time.perf_counter() - t0
            print(f"   -> [LỖI NGOẠI LỆ] {err} (sau {elapsed:.2f}s)")

    print("\n==================== TỔNG KẾT THỬ NGHIỆM ====================")
    print(f"Lô thử nghiệm      : {lot_id} - {title[:50]}...")
    print(f"Tổng số ảnh của lô : {len(image_urls)} ảnh")
    print(f"Số ảnh test upload : {len(test_subset)}")
    print(f"Tỷ lệ thành công   : {success_count}/{len(test_subset)} ({success_count/len(test_subset)*100:.0f}%)")
    if results:
        print("\nDanh sách link Catbox đã lưu thành công:")
        for orig, cb, sz in results:
            print(f" - {cb} ({sz:,} bytes)")

if __name__ == "__main__":
    main()
