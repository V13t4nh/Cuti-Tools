# Bàn giao Buyer deal evaluation

## 1. Commit hash + ngày đóng gói

- Source commit: `774b89e8b00d412496a13f0289f5c6fc09406f83`
- Ngày đóng gói: 2026-08-19 (Asia/Bangkok)
- `NOTION_SANDBOX/PROVENANCE.json` ghi cùng source commit.

## 2. Output verify thật, nguyên văn

Máy Windows này không có GNU `make`; đã chạy trực tiếp thân lệnh `verify` bằng Python project-local, offline và không cài package:

```text
> D:\Projects\cuti-tools\.venv\Scripts\python.exe -m unittest discover -s tests -v

----------------------------------------------------------------------
Ran 264 tests in 9.060s

OK

VERIFY OK — artifacts: D:\Projects\cuti-tools\var\verify\12c39ed7710b
exit code: 0
```

Kết quả: 264 passed, 0 failed, 0 skipped. `scripts/verify.py` là thân lệnh của target `make verify` sau bước kiểm tra/generate sample fixture.

## 3. File thêm / sửa / xoá, kèm LOC sau khi sửa

Sửa:

- `src/cuti/app.py` — 94 LOC
- `src/cuti/cli.py` — 84 LOC
- `src/cuti/cli_commands.py` — 125 LOC
- `src/cuti/cli_parser.py` — 74 LOC
- `NOTION_SANDBOX/PROVENANCE.json` — 11 LOC
- `notion.md` — 59 LOC

Thêm:

- `src/cuti/evaluation.py` — 154 LOC
- `tests/test_evaluation.py` — 115 LOC

Xoá: không có.

Diff schema: không đổi bảng, cột hoặc index; `src/cuti/storage/schema_ddl.py` không bị sửa.

## 4. Từng task được giao

- T1: thêm `DealEvaluation`, `cost_to_eur` và `evaluate_deal` thuần. Evaluator tái dùng `find_comparables` và `pricing.quote`, không ghi DB/network và là nơi duy nhất có logic quyết định.
- T2: thay app Streamlit bằng một màn hình Buyer ba bước; app chỉ lấy input, gọi helper/evaluator và render. Optional import Streamlit vẫn nằm trong hàm UI.
- T3: thêm `cuti evaluate --query <text> --cost <số> --currency vnd|eur --condition <tag>`, luôn in JSON của evaluator.
- T4: thêm test offline cho percentile/verdict, insufficient_data không có Net Profit, VND/EUR tương đương, tách naked/fullset bằng giá khác nhau và loại pending-review. Chỉ số thanh khoản hiển thị là sell-through của tập comparable cùng mã/cụm tình trạng.

## 5. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Không có câu hỏi mới. Không thêm dependency, không sửa `pricing.py`, `config/rules.json` hoặc DDL.
- GNU Make/WSL không được cài trên máy đóng gói nên không chạy được literal `make verify`; thân verify chạy xanh như mục 2. Sandbox có GNU Make cần chạy lại literal `make verify`.
- `insufficient_data` giữ cả ba Net Profit là `None`; evaluator không đoán số. Cost không hợp lệ (kể cả boolean/NaN/infinity) trả `PricingError` có kiểu.
- Quy ước hash: source commit ở mục 1 chứa mã/test; commit tài liệu sau đó không thể tự tham chiếu chính hash của nó mà không làm thay đổi hash.
