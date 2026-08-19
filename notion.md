# Bàn giao Scale 1 Buyer: chu kỳ + gia tốc tim

## 1. Commit hash + ngày đóng gói

- Source commit: `83f2137c0f508d00426810aa16ef1d4eece4a662`
- Ngày đóng gói: 2026-08-19 (Asia/Bangkok)
- `NOTION_SANDBOX/PROVENANCE.json` ghi cùng source commit.

## 2. Output verify thật, nguyên văn

Máy Windows này không có GNU `make`; đã chạy trực tiếp thân lệnh `verify` bằng Python project-local, offline và không cài package:

```text
> D:\\Projects\\cuti-tools\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v

----------------------------------------------------------------------
Ran 279 tests in 11.865s

OK

VERIFY OK — artifacts: D:\\Projects\\cuti-tools\\var\\verify\\a8461dd084e0
exit code: 0
```

Kết quả: 279 passed, 0 failed, 0 skipped. `scripts/verify.py` là thân lệnh của target `make verify` và đã chạy offline.

## 3. File thêm / sửa / xoá, kèm LOC sau khi sửa

Sửa:

- `src/cuti/app.py` — 121 LOC
- `src/cuti/charts.py` — 219 LOC
- `src/cuti/evaluation.py` — 188 LOC
- `tests/test_evaluation.py` — 225 LOC
- `NOTION_SANDBOX/PROVENANCE.json` — 11 LOC
- `notion.md` — 60 LOC

Thêm:

- `src/cuti/evaluation_chart.py` — 171 LOC
- `tests/test_charts_cycle.py` — 65 LOC

Xoá: không có.

Diff schema: không đổi bảng, cột hoặc index; `src/cuti/storage/schema_ddl.py` không bị sửa.

## 4. Từng task được giao

- T1: thêm `evaluate_deal_with_chart`, trả `BuyerEvaluation(decision, chart)` từ một pool comparable và đúng một lần gọi `pricing.quote`. `evaluate_deal`/CLI giữ nguyên JSON 15 khoá; có test spy xác nhận một quote cho một lượt Buyer.
- T2: tách chart/pool sang `evaluation_chart.py`; `evaluation.py` chỉ giữ logic quyết định. Mọi file `src/cuti` hiện không vượt 230 LOC.
- T3: thêm `cycle_position` thuần stdlib, so median quý mới nhất với dãy median quý của window; thiếu 3 quý trả `None`. UI gán nhãn khác biệt “Vị trí giá hoà vốn trong pool” và “Vị trí chu kỳ”.
- T4: thêm `heart_acceleration_rate` thuần stdlib, so sánh trung bình hearts/ngày hai cửa sổ liền kề; dùng lại `_heart_speed` cho report. UI chỉ hiện gia tốc tim khi có dữ liệu. Test bao phủ nóng lên, nguội đi và thiếu mẫu.
- Kiểm chứng regression: sample EUR 1000 vẫn green, `sample_size=8`, Net Profit p25/median/p75 `1382.0278125 / 1522.28375 / 1827.6215625`; VNĐ 27000000 xuất JSON giống từng ký tự; output `cuti liquidity` trong verify không đổi.

## 5. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Không có câu hỏi chờ duyệt. `cycle_position` dùng ngưỡng 3 quý theo quy ước quarterly trend đang có: signature thuần không nhận Settings và repo không có env “số quý tối thiểu”; không thêm env hoặc đổi contract ngoài spec.
- Không thêm dependency hoặc env; không sửa DDL, `config/rules.json`, Details live hay `pricing.py`.
- GNU Make/WSL không được cài trên máy đóng gói nên không chạy được literal `make verify`; thân verify chạy xanh như mục 2. Sandbox có GNU Make cần chạy lại literal `make verify`.
- Quy ước hash: source commit ở mục 1 chứa mã/test; commit tài liệu sau đó không thể tự tham chiếu chính hash của nó mà không làm thay đổi hash.
