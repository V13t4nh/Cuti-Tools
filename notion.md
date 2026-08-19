# Bàn giao P0 identity + adapter Catawiki

## 1. Commit hash + ngày đóng gói

- Source commit: `6318564f27ae89e4d3bc5aa35a338c4c9a1bc781`
- Ngày đóng gói: 2026-08-19 (Asia/Bangkok)
- `NOTION_SANDBOX/PROVENANCE.json` ghi cùng source commit trên.

## 2. Output verify thật, nguyên văn

```text
Ran 250 tests in 8.003s

OK

VERIFY OK — artifacts: D:\Projects\cuti-tools\var\verify\5bc583f6b144
exit code: 0
```

Lệnh đã chạy offline, không cài package:

```text
PYTHONPATH=src;tests .\.venv\Scripts\python.exe scripts\verify.py
```

Kết quả: 250 passed, 0 failed, 0 skipped. Máy Windows hiện tại không có GNU `make`; thân lệnh `make verify` đã chạy thành công như trên. Sandbox có GNU Make cần chạy lại literal `make verify`.

## 3. File thêm / sửa / xoá, kèm LOC sau khi sửa

Sửa:

- `NOTION_SANDBOX/PROVENANCE.json` — 11 LOC
- `config/rules.json` — 60 LOC
- `src/cuti/normalize_identity.py` — 93 LOC
- `src/cuti/pipeline/report.py` — 227 LOC
- `src/cuti/pipeline/settlement.py` — 168 LOC
- `src/cuti/pipeline/settlement_resolver.py` — 247 LOC
- `src/cuti/storage/lots.py` — 203 LOC

Thêm:

- `AGENTS.md` — 63 LOC
- `tests/test_identity_reference_shapes.py` — 51 LOC
- `tests/test_t2_settlement_details.py` — 75 LOC

Xoá: không có.

Diff schema: không đổi bảng, cột hoặc index. Lưu `lot_desc` dùng schema v4 đã nghiệm thu; thay đổi lượt này chỉ nối Details/description vào đường settle thật.

Mọi file `src/cuti` chạm trong lượt này <= 250 LOC. Ngoài scope còn: `scrapers/catawiki_api.py` 362, `cli.py` 360, `config.py` 302 LOC.

## 4. Từng task được giao

- T1: xoá ba modern-ref fixture khỏi config; dùng regex hình dạng generic, xét modern trước split, và chỉ split Seiko/Citizen vintage 4 ký tự - 4 ký tự. Đã có assert riêng cho đủ Seiko, Citizen vintage/modern, Rolex hai dạng, Longines và Omega Cal. 503 từ description.
- T2: thêm `fetch_details` optional vào `settle`; `pipeline/report.py` dùng `fetch_text` sẵn có để CLI path truyền HTML lot page vào parser. Fetch lỗi/None vẫn lưu lot; buyer JSON vẫn là nguồn duy nhất của hammer/sold/ngày, `ai_json` vẫn NULL. Đã bỏ duck-typing/filter im lặng và test end-to-end xác nhận typed fields, `model_key_tier`, `needs_review` enum lạ và `lot_desc` zlib.
- T3: provenance cập nhật `testsRun=250`, `testsPassed=250`, `testsFailed=0`, `exitCode=0`.

## 5. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Không có câu hỏi mới. Không thêm HTTP client, dependency, ảnh hoặc HTML thô; chỉ dùng `fetch.py` hiện có.
- Quy ước hash: `notion.md` và `PROVENANCE.json` cùng trỏ source commit ở mục 1. Commit tài liệu/đóng gói chứa chính hash không thể tự tham chiếu mà không đổi hash; nó không thay đổi source behavior.
