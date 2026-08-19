# Bàn giao T5 Buyer unit boundary + Scale 1

## 1. Commit hash + ngày đóng gói

- Source commit: `3199c283cdd5755fd3cecc381dd3897879bb343d`
- Ngày đóng gói: 2026-08-19 (Asia/Bangkok)
- `NOTION_SANDBOX/PROVENANCE.json` ghi cùng source commit.

## 2. Output verify thật, nguyên văn

Máy Windows này không có GNU `make`; đã chạy trực tiếp thân lệnh `verify` bằng Python project-local, offline và không cài package:

```text
> D:\\Projects\\cuti-tools\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v

----------------------------------------------------------------------
Ran 271 tests in 9.493s

OK

VERIFY OK — artifacts: D:\\Projects\\cuti-tools\\var\\verify\\5e2abc331a5c
exit code: 0
```

Kết quả: 271 passed, 0 failed, 0 skipped. `scripts/verify.py` là thân lệnh của target `make verify` và đã chạy offline.

## 3. File thêm / sửa / xoá, kèm LOC sau khi sửa

Sửa:

- `README.md` — 218 LOC
- `src/cuti/app.py` — 128 LOC
- `src/cuti/charts.py` — 170 LOC
- `src/cuti/cli_commands.py` — 123 LOC
- `src/cuti/evaluation.py` — 242 LOC
- `tests/test_evaluation.py` — 182 LOC
- `NOTION_SANDBOX/PROVENANCE.json` — 11 LOC
- `notion.md` — 59 LOC

Thêm:

- `tests/test_charts_scale1.py` — 41 LOC

Xoá: không có.

Diff schema: không đổi bảng, cột hoặc index; `src/cuti/storage/schema_ddl.py` không bị sửa.

## 4. Từng task được giao

- T5: `evaluate_deal` nhận input thô `cost` + `currency`. Nhánh VNĐ truyền số VNĐ trực tiếp cho `pricing.quote`; nhánh EUR chỉ nhân tỷ giá một lần tại evaluator. CLI và UI chỉ chuyển input thô. Test spy chặn việc gọi `cost_to_eur` trên nhánh VNĐ. Với sample DB, EUR 1000 và VNĐ 27000000 xuất JSON giống từng ký tự; Net Profit p25/median/p75 giữ `1382.0278125 / 1522.28375 / 1827.6215625`.
- T2: README làm rõ `CUTI_MIN_COMPARABLES` xét số lot đã bán cho verdict; hai rate thanh khoản chỉ tính khi tổng pool đạt ngưỡng. Ví dụ 6 lot, 2 lot bán: `insufficient_data` và `sell_through_rate = 0.33`, không suy đoán Net Profit.
- T3: thêm `hammer_histogram` và `price_position` thuần stdlib, có test bin/empty/duplicate. `comparison_chart_data` tách dữ liệu biểu đồ khỏi `DealEvaluation`, ẩn pool thiếu mẫu. UI chỉ render từ helper; không thêm dependency hay số học bin trong `app.py`.

## 5. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Không có câu hỏi chờ duyệt. `pricing.quote` vẫn giữ contract VNĐ và không bị sửa; evaluator là ranh giới quy đổi duy nhất theo quyết định đã duyệt.
- Không thêm dependency hoặc env; không sửa DDL, `config/rules.json`, đường Details live hay `pricing.py`.
- GNU Make/WSL không được cài trên máy đóng gói nên không chạy được literal `make verify`; thân verify chạy xanh như mục 2. Sandbox có GNU Make cần chạy lại literal `make verify`.
- Quy ước hash: source commit ở mục 1 chứa mã/test; commit tài liệu sau đó không thể tự tham chiếu chính hash của nó mà không làm thay đổi hash.
