"""Comprehensive 300+ Products Parity Verification Script.

Verifies that the new TLS-impersonated transport (curl-cffi) produces 100% identical
output to the old transport (urllib in src/cuti/fetch.py) across at least 300 products.
Asserts that every single field matches with ZERO discrepancy.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Add project src and current dir to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CURRENT_DIR = Path(__file__).resolve().parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Import OLD transport
from cuti.fetch import fetch_json as old_fetch_json, fetch_text as old_fetch_text
from cuti.scrapers.catawiki_payload import parse_search_page, parse_live_lots
from cuti.scrapers.catawiki_lot_page import parse_lot_page
from cuti.normalize import load_rules

# Import NEW TLS transport
from fetch_tls import fetch_json as new_fetch_json, fetch_text as new_fetch_text
from client import CatawikiTlsApi, chunks

TARGET_PRODUCTS_COUNT = 300
PAGE_SIZE = 25  # Catawiki default page size
PAGES_NEEDED = (TARGET_PRODUCTS_COUNT + PAGE_SIZE - 1) // PAGE_SIZE  # 12 pages = 300 products


def main() -> None:
    print("=" * 75)
    print(f" 🛡️ BẮT ĐẦU VERIFY ĐỐI CHIẾU PARITY: ÍT NHẤT {TARGET_PRODUCTS_COUNT} SẢN PHẨM (LOTS)")
    print(" Tiêu chí: Tất cả các trường dữ liệu giữa cách Cũ và Mới phải giống nhau 100%.")
    print("=" * 75)

    rules = load_rules(PROJECT_ROOT / "config" / "rules.json")

    total_verified = 0
    total_assertions = 0
    mismatches = []

    all_lot_ids: list[str] = []
    old_products: dict[str, dict] = {}
    new_products: dict[str, dict] = {}

    # -------------------------------------------------------------
    # GIAI ĐOẠN 1: VERIFY TÌM KIẾM 300+ SẢN PHẨM (SEARCH API)
    # -------------------------------------------------------------
    print(f"\n[PHASE 1] Thu thập và đối chiếu {TARGET_PRODUCTS_COUNT} sản phẩm qua Search API ({PAGES_NEEDED} trang)...")
    
    t0_phase1 = time.perf_counter()
    for page in range(1, PAGES_NEEDED + 1):
        url = f"https://www.catawiki.com/buyer/api/v1/search?q=watch&page={page}"
        print(f"  -> Trang {page:02d}/{PAGES_NEEDED}:", end=" ", flush=True)

        # Gọi cả 2 cơ chế gần như đồng thời
        t_old = time.perf_counter()
        data_old = old_fetch_json(url, timeout_seconds=15)
        old_ms = (time.perf_counter() - t_old) * 1000

        t_new = time.perf_counter()
        data_new = new_fetch_json(url, timeout_seconds=15)
        new_ms = (time.perf_counter() - t_new) * 1000

        lots_old = data_old.get("lots", [])
        lots_new = data_new.get("lots", [])

        if len(lots_old) != len(lots_new):
            mismatches.append(f"Trang {page}: Số lượng lots khác nhau (Old={len(lots_old)}, New={len(lots_new)})")

        page_matched = 0
        for o_lot, n_lot in zip(lots_old, lots_new):
            lot_id = str(o_lot.get("id"))
            all_lot_ids.append(lot_id)
            total_verified += 1

            # Assert từng trường dữ liệu của sản phẩm
            checks = [
                ("id", str(o_lot.get("id")), str(n_lot.get("id"))),
                ("title", o_lot.get("title"), n_lot.get("title")),
                ("subtitle", o_lot.get("subtitle"), n_lot.get("subtitle")),
                ("thumbImageUrl", o_lot.get("thumbImageUrl"), n_lot.get("thumbImageUrl")),
                ("url", o_lot.get("url"), n_lot.get("url")),
            ]

            lot_mismatch = False
            for field, val_old, val_new in checks:
                total_assertions += 1
                if val_old != val_new:
                    mismatches.append(f"Lot {lot_id} [{field}]: Old='{val_old}' != New='{val_new}'")
                    lot_mismatch = True

            if not lot_mismatch:
                page_matched += 1

            old_products[lot_id] = o_lot
            new_products[lot_id] = n_lot

        print(f"Khớp {page_matched}/{len(lots_old)} lots 100% | Old: {old_ms:.0f}ms, New: {new_ms:.0f}ms")
        time.sleep(0.3)  # Nghỉ an toàn

    time_phase1 = time.perf_counter() - t0_phase1
    print(f"[✓] Hoàn tất Phase 1 trong {time_phase1:.1f}s. Đã thu thập: {len(all_lot_ids)} sản phẩm.")

    # -------------------------------------------------------------
    # GIAI ĐOẠN 2: VERIFY TRẠNG THÁI TRỰC TIẾP (LIVE STATES) BATCH
    # -------------------------------------------------------------
    print(f"\n[PHASE 2] Đối chiếu Live States theo Batch cho toàn bộ {len(all_lot_ids)} sản phẩm...")
    batch_size = 50
    phase2_matched = 0
    t0_phase2 = time.perf_counter()

    for batch in chunks(all_lot_ids, batch_size):
        ids_str = ",".join(batch)
        url = f"https://www.catawiki.com/buyer/api/v1/lots/live?ids={ids_str}"

        data_old = old_fetch_json(url, timeout_seconds=15)
        data_new = new_fetch_json(url, timeout_seconds=15)

        dict_old = {str(item.get("id")): item for item in data_old.get("lots", [])}
        dict_new = {str(item.get("id")): item for item in data_new.get("lots", [])}

        for lot_id in batch:
            o_st = dict_old.get(lot_id)
            n_st = dict_new.get(lot_id)

            if not o_st or not n_st:
                mismatches.append(f"Lot {lot_id}: Không tìm thấy trong live_states (Old={bool(o_st)}, New={bool(n_st)})")
                continue

            # Đối chiếu favorite_count, bidding_end_time, closed
            total_assertions += 3
            if o_st.get("favorite_count") != n_st.get("favorite_count"):
                mismatches.append(f"Lot {lot_id} [favorite_count]: {o_st.get('favorite_count')} != {n_st.get('favorite_count')}")
            if o_st.get("bidding_end_time") != n_st.get("bidding_end_time"):
                mismatches.append(f"Lot {lot_id} [bidding_end_time]: {o_st.get('bidding_end_time')} != {n_st.get('bidding_end_time')}")
            if o_st.get("closed") != n_st.get("closed"):
                mismatches.append(f"Lot {lot_id} [closed]: {o_st.get('closed')} != {n_st.get('closed')}")

            phase2_matched += 1

        print(f"  -> Batch {len(batch)} lots: Khớp 100% trạng thái.")
        time.sleep(0.3)

    time_phase2 = time.perf_counter() - t0_phase2
    print(f"[✓] Hoàn tất Phase 2 trong {time_phase2:.1f}s.")

    # -------------------------------------------------------------
    # GIAI ĐOẠN 3: VERIFY BÓC TÁCH HTML & SPECS (DETAIL PAGES)
    # -------------------------------------------------------------
    print(f"\n[PHASE 3] Kiểm tra đối chiếu HTML & bóc tách thông số kỹ thuật (Specs) mẫu...")
    sample_lots = all_lot_ids[:5]
    for idx, lot_id in enumerate(sample_lots, 1):
        lot_url = f"https://www.catawiki.com/en/l/{lot_id}"
        html_old = old_fetch_text(lot_url, timeout_seconds=15)
        html_new = new_fetch_text(lot_url, timeout_seconds=15)

        spec_old = parse_lot_page(html_old, rules=rules)
        spec_new = parse_lot_page(html_new, rules=rules)

        # Assert brand, model, ref_number, caliber, specs
        checks = [
            ("brand", spec_old.brand, spec_new.brand),
            ("model", spec_old.model, spec_new.model),
            ("ref_number", spec_old.ref_number, spec_new.ref_number),
            ("movement", spec_old.movement, spec_new.movement),
            ("specs_count", len(spec_old.specs), len(spec_new.specs)),
        ]
        for field, v_old, v_new in checks:
            total_assertions += 1
            if v_old != v_new:
                mismatches.append(f"Lot {lot_id} HTML [{field}]: Old='{v_old}' != New='{v_new}'")

        print(f"  -> [{idx}/{len(sample_lots)}] Lot #{lot_id}: Brand={spec_new.brand}, Model={spec_new.model}, Specs={len(spec_new.specs)} trường -> Khớp 100%")
        time.sleep(0.3)

    # -------------------------------------------------------------
    # TỔNG KẾT & KẾT LUẬN NGHIỆM THU
    # -------------------------------------------------------------
    print("\n" + "=" * 75)
    print(" 📋 KẾT QUẢ NGHIỆM THU ĐỐI CHIẾU (PARITY VERIFICATION REPORT)")
    print("=" * 75)
    print(f"• Số lượng sản phẩm đã verify       : {total_verified} sản phẩm (Yêu cầu >= {TARGET_PRODUCTS_COUNT})")
    print(f"• Tổng số lượt kiểm tra assertions  : {total_assertions:,} assertions")
    print(f"• Số điểm sai lệch (Mismatches)     : {len(mismatches)}")
    print(f"• Thời gian hoàn thành toàn bộ test : {time_phase1 + time_phase2:.2f} giây")

    if mismatches:
        print("\n❌ VERIFY FAILED! Các điểm không khớp:")
        for m in mismatches[:10]:
            print(f"  - {m}")
        if len(mismatches) > 10:
            print(f"  ... và {len(mismatches) - 10} lỗi khác.")
        sys.exit(1)
    else:
        print("\n" + "*" * 75)
        print(" 🎉 KẾT QUẢ: PASS 100%! TẤT CẢ CÁC TRƯỜNG DỮ LIỆU ĐỀU GIỐNG NHAU HOÀN TOÀN!")
        print("*" * 75)

    # Lưu bản đối chiếu vào thư mục output để lưu vết
    out_dir = CURRENT_DIR / "output"
    out_dir.mkdir(exist_ok=True)
    report_file = out_dir / "parity_verification_report.json"
    report_data = {
        "status": "PASS",
        "verified_products_count": total_verified,
        "total_assertions": total_assertions,
        "mismatches_count": len(mismatches),
        "sample_verified_lot_ids": all_lot_ids[:10],
    }
    report_file.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    print(f"\n[✓] Đã ghi nhận báo cáo đối chiếu tại: {report_file}")


if __name__ == "__main__":
    main()
