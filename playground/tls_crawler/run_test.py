"""Interactive runner / demo script for the TLS Impersonation Crawler."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from crawler import CatawikiTlsCrawler


def main() -> None:
    parser = argparse.ArgumentParser(description="Test TLS Impersonation Crawler against Catawiki.")
    parser.add_argument("--query", "-q", default="Omega Speedmaster", help="Từ khóa tìm kiếm (mặc định: 'Omega Speedmaster')")
    parser.add_argument("--limit", "-n", type=int, default=3, help="Số lượng lots cần kiểm tra chi tiết (mặc định: 3)")
    parser.add_argument("--pause", "-p", type=float, default=0.8, help="Độ trễ an toàn giữa các request tính bằng giây (mặc định: 0.8s)")
    args = parser.parse_args()

    print("=" * 65)
    print(" 🚀 THỬ NGHIỆM CÀO DỮ LIỆU CATAWIKI BẰNG GIẢ LẬP TLS (curl-cffi)")
    print("=" * 65)
    print(f"• Từ khóa tìm kiếm    : '{args.query}'")
    print(f"• Số lượng lot lấy thử: {args.limit}")
    print(f"• Độ trễ an toàn      : {args.pause}s / request")
    print("-" * 65)

    crawler = CatawikiTlsCrawler(impersonate="chrome124", pause_seconds=args.pause)

    # 1. Tìm kiếm lots đang mở
    total, lots = crawler.search(args.query, page=1)
    print(f"\n[+] Tổng số lots tìm thấy trên sàn: {total:,} lots")

    if not lots:
        print("[!] Không tìm thấy lot nào phù hợp.")
        return

    selected = lots[: args.limit]
    print(f"[+] Đang lấy trạng thái trực tiếp cho {len(selected)} lots đầu tiên...")

    # 2. Lấy thông tin đấu giá trực tiếp (giá bid, favorite, ngày đóng)
    crawler.fill_live_states(selected)

    # 3. Lấy thông số kỹ thuật chi tiết từ HTML trang lot
    print("\n[+] Đang bóc tách thông số kỹ thuật (Specs & Details) từ HTML...")
    for idx, lot in enumerate(selected, 1):
        print(f"  [{idx}/{len(selected)}] Lot #{lot.lot_id}: {lot.title[:50]}...")
        try:
            crawler.fetch_lot_details(lot)
        except Exception as e:
            print(f"    [!] Lỗi bóc tách: {e}")

    # 4. Hiển thị bảng tổng kết
    print("\n" + "=" * 65)
    print(" 📋 KẾT QUẢ THU HOẠCH DỮ LIỆU")
    print("=" * 65)
    for idx, lot in enumerate(selected, 1):
        print(f"\n--- LOT #{idx}: ID {lot.lot_id} ---")
        print(f" Tiêu đề      : {lot.title}")
        print(f" Giá bid hiện : {lot.current_bid_eur} EUR" if lot.current_bid_eur else " Giá bid hiện : Chưa có")
        print(f" Lượt thích   : {lot.favorite_count} ❤️")
        print(f" Hạn chốt     : {lot.bidding_end_time}")
        print(f" Nhận diện    : Brand={lot.brand or 'N/A'}, Model={lot.model or 'N/A'}, Ref={lot.ref_number or 'N/A'}")
        if lot.specs:
            specs_summary = ", ".join(f"{k}: {v}" for k, v in list(lot.specs.items())[:4])
            print(f" Thông số mẫu : {specs_summary}")
        print(f" Link gốc     : {lot.url}")

    # 5. Lưu ra file JSON
    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "crawled_sample.json"

    data = [asdict(l) for l in selected]
    out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "-" * 65)
    print(f"[✓] Đã lưu kết quả chi tiết ra: {out_file}")
    print("=" * 65)


if __name__ == "__main__":
    main()
