# Bàn giao dọn nợ Buyer liquidity

## 1. Commit hash + ngày đóng gói

- Source commit: `6115cb9c69f85ce341b889fc4f0f31a22dde215c`
- Ngày đóng gói: 2026-08-19 (Asia/Bangkok)
- `NOTION_SANDBOX/PROVENANCE.json` ghi cùng source commit.

## 2. Output verify thật, nguyên văn

Máy Windows này không có GNU `make`; đã chạy trực tiếp thân lệnh `verify` bằng Python project-local, offline và không cài package:

```text
> D:\Projects\cuti-tools\.venv\Scripts\python.exe -m unittest discover -s tests -v

----------------------------------------------------------------------
Ran 267 tests in 8.082s

OK

VERIFY OK — artifacts: D:\Projects\cuti-tools\var\verify\fd51f1536ccb
exit code: 0
```

Kết quả: 267 passed, 0 failed, 0 skipped. `scripts/verify.py` là thân lệnh của target `make verify` sau bước kiểm tra/generate sample fixture.

## 3. File thêm / sửa / xoá, kèm LOC sau khi sửa

Sửa:

- `AGENTS.md` — 63 LOC
- `src/cuti/app.py` — 102 LOC
- `src/cuti/cli_commands.py` — 122 LOC
- `src/cuti/evaluation.py` — 150 LOC
- `src/cuti/liquidity.py` — 151 LOC
- `tests/test_evaluation.py` — 176 LOC
- `NOTION_SANDBOX/PROVENANCE.json` — 11 LOC
- `notion.md` — 58 LOC

Thêm: không có. Xoá: không có.

Diff schema: không đổi bảng, cột hoặc index; `src/cuti/storage/schema_ddl.py` không bị sửa.

## 4. Từng task được giao

- T1: `DealEvaluation` dùng `sell_through_rate` và `heart_to_hammer_rate`; tim→hammer gọi lại helper chung trong `liquidity.py`. Pool dưới `CUTI_MIN_COMPARABLES` trả cả hai là `None`; không có lot hot trả tim→hammer `None`.
- T2: xoá alias Net Profit/liquidity và JSON `cuti evaluate` chỉ còn một key cho mỗi giá trị.
- T3: `app.py` bỏ duck typing, đọc typed field trực tiếp và hiển thị sell-through, ngày trung bình chốt, tim→hammer.
- T4: sửa test VND/EUR đi qua hai nhánh thật; thêm test hot sold/unsold, no-hot, all-sold/half-sold và JSON key set.
- T5: chưa đổi được contract một chiều theo lệnh dừng ở mục 5; output sample không đổi: query `Omega Seamaster Diver 300M 210.30.42`, `1000 EUR`, `naked` cho p25/median/p75 `1382.0278125 / 1522.28375 / 1827.6215625`.
- T6: điền bối cảnh verify, LOC và stack/ràng buộc bền vào `AGENTS.md`.

## 5. Phản biện spec, câu hỏi, thứ cần xin duyệt

- T5 có xung đột contract: `evaluate_deal` nhận EUR, nhưng `pricing.quote` công khai chỉ nhận VNĐ. Để bỏ EUR→VNĐ→EUR phải sửa `pricing.py` hoặc lặp orchestration pricing; prompt cấm cả sửa `pricing.py` lẫn vi phạm DRY. Theo lệnh, không sửa `pricing.py`; giữ round-trip hiện tại để output không đổi. Cần duyệt rõ một trong hai thay đổi cho lượt sau nếu muốn đóng T5.
- Không thêm dependency, không sửa DDL hay `config/rules.json`.
- GNU Make/WSL không được cài trên máy đóng gói nên không chạy được literal `make verify`; thân verify chạy xanh như mục 2. Sandbox có GNU Make cần chạy lại literal `make verify`.
- Quy ước hash: source commit ở mục 1 chứa mã/test; commit tài liệu sau đó không thể tự tham chiếu chính hash của nó mà không làm thay đổi hash.
