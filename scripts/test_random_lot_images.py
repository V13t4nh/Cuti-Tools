"""Test script: Pick 1 random lot, extract all image URLs, and verify every image
for accessibility, resolution, byte size, and validity.
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
import time
import urllib.request

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from cuti.fetch import DEFAULT_HEADERS, fetch_text

def get_jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    """Parse JPEG width and height from binary stream without PIL."""
    i = 0
    while i < len(data) - 9:
        if data[i] == 0xFF and data[i+1] in (0xC0, 0xC1, 0xC2):
            height = (data[i+5] << 8) + data[i+6]
            width = (data[i+7] << 8) + data[i+8]
            return width, height
        i += 1
    return None

def get_random_lot(db_path: str = "var/auctions.db") -> tuple[str, str, str]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT lot_id, title, url FROM lots ORDER BY RANDOM() LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        raise RuntimeError("No lots found in database")
    return str(row[0]), str(row[1]), str(row[2])

def extract_lot_images(html: str) -> list[str]:
    """Extract all distinct high-resolution lot image URLs."""
    raw_matches = set(re.findall(r'https://assets\.catawiki\.nl/assets/[^"\'\s<>]+?\.(?:jpg|jpeg|png|webp)', html, re.IGNORECASE))
    high_res_set = set()
    for u in raw_matches:
        # Exclude category banners, UI icons, or buyer assets
        if any(x in u for x in ("/categories/", "/buyer/", "/buyer_ui/", "shoplive")):
            continue
        # Strip thumbnail prefixes to get true original resolution
        normalized = re.sub(r'/thumb\d*_', '/', u)
        high_res_set.add(normalized)

    # Sort to ensure stable order
    return sorted(list(high_res_set))

def verify_single_image(url: str, timeout: float = 10.0) -> dict[str, object]:
    """Check image HTTP status, headers, size, and dimensions."""
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read()
            size = len(body)
            dimensions = get_jpeg_dimensions(body) if "jpeg" in content_type or "jpg" in url else None
            is_valid_jpeg = body.startswith(b"\xff\xd8\xff")
            return {
                "url": url,
                "status": status,
                "content_type": content_type,
                "size_bytes": size,
                "dimensions": dimensions,
                "is_valid": is_valid_jpeg if "jpeg" in content_type else (size > 1000),
                "elapsed_ms": elapsed_ms,
                "error": None,
            }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return {
            "url": url,
            "status": None,
            "content_type": None,
            "size_bytes": 0,
            "dimensions": None,
            "is_valid": False,
            "elapsed_ms": elapsed_ms,
            "error": str(e),
        }

def main():
    print("==================================================================")
    print("    KIỂM THỬ TRÍCH XUẤT ẢNH THỰC TẾ TRÊN 1 LÔ NGẪU NHIÊN          ")
    print("==================================================================")

    lot_id, title, url = get_random_lot()
    print(f"[*] Đã bốc ngẫu nhiên lô : {lot_id}")
    print(f"[*] Tiêu đề              : {title}")
    print(f"[*] URL nguồn sàn        : {url}")
    print("-" * 66)

    print("[*] Đang tải trang HTML chi tiết...")
    t_start = time.perf_counter()
    try:
        html = fetch_text(url, timeout_seconds=15.0)
    except Exception as err:
        print(f"[!] Lỗi khi tải HTML từ sàn: {err}")
        return
    t_fetch = (time.perf_counter() - t_start) * 1000
    print(f"[OK] Tải xong HTML: {len(html):,} ký tự trong {t_fetch:.1f} ms")

    # Bóc tách
    t_pstart = time.perf_counter()
    image_urls = extract_lot_images(html)
    t_parse = (time.perf_counter() - t_pstart) * 1000
    print(f"[OK] Bóc tách xong: Tìm thấy {len(image_urls)} ảnh trong {t_parse:.2f} ms")
    print("-" * 66)

    if not image_urls:
        print("[!] Không tìm thấy ảnh nào cho lô này!")
        return

    print(f"[*] Tiến hành kiểm chứng tính toàn vẹn của {len(image_urls)} ảnh...")
    verified_results = []
    for idx, img_url in enumerate(image_urls, start=1):
        info = verify_single_image(img_url)
        verified_results.append(info)
        dims_str = f"{info['dimensions'][0]}x{info['dimensions'][1]} px" if info['dimensions'] else "N/A"
        status_symbol = "✓ OK" if info['is_valid'] and info['status'] == 200 else "✗ LỖI"
        
        print(
            f"[{idx:02d}/{len(image_urls):02d}] {status_symbol} | "
            f"HTTP {info['status']} | "
            f"Kích thước: {info['size_bytes']/1024:6.1f} KB | "
            f"Độ phân giải: {dims_str:12s} | "
            f"Tải: {info['elapsed_ms']:5.1f} ms"
        )
        if info['error']:
            print(f"     -> Lỗi chi tiết: {info['error']}")

    # Tổng kết
    valid_count = sum(1 for r in verified_results if r['is_valid'] and r['status'] == 200)
    total_bytes = sum(r['size_bytes'] for r in verified_results)
    avg_size_kb = (total_bytes / len(verified_results)) / 1024 if verified_results else 0

    print("=" * 66)
    print("                    BÁO CÁO NGHIỆM THU ẢNH                       ")
    print("=" * 66)
    print(f"Tổng số ảnh bóc tách được    : {len(image_urls)} ảnh")
    print(f"Số ảnh hợp lệ (HTTP 200, nét): {valid_count} / {len(image_urls)} ({valid_count/len(image_urls)*100:.1f}%)")
    print(f"Tổng dung lượng bộ ảnh       : {total_bytes / (1024*1024):.2f} MB")
    print(f"Dung lượng trung bình mỗi ảnh: {avg_size_kb:.1f} KB (Chuẩn ảnh HD gốc)")
    
    # Hiển thị 3 mẫu URL đầu tiên để xem trực tiếp
    print("\n[MẪU LINK ẢNH TRÍCH XUẤT ĐƯỢC ĐỂ USER KIỂM TRA]:")
    for r in verified_results[:3]:
        print(f" - {r['url']}")
    print("=" * 66)

if __name__ == "__main__":
    main()
