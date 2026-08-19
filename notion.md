# Bàn giao live Catawiki Lot Details

## 1. Commit hash + ngày đóng gói

- Source commit: `16933a8f5ebe7eabdb456802c8d28200510f03df`
- Ngày đóng gói: 2026-08-19 (Asia/Bangkok)
- `NOTION_SANDBOX/PROVENANCE.json` ghi cùng source commit.

## 2. Output verify thật, nguyên văn

Máy Windows này không có GNU `make`; đã chạy trực tiếp thân lệnh `verify` bằng Python project-local, offline, không cài package và không gọi mạng (Details mặc định tắt):

```text
> D:\Projects\cuti-tools\.venv\Scripts\python.exe -m unittest discover -s tests -v

----------------------------------------------------------------------
Ran 256 tests in 11.238s

OK

VERIFY OK — artifacts: D:\Projects\cuti-tools\var\verify\259dabe31ed6
exit code: 0
```

Kết quả: 256 passed, 0 failed, 0 skipped. `scripts/verify.py` là thân lệnh của target `make verify` sau bước kiểm tra/generate sample fixture.

## 3. File thêm / sửa / xoá, kèm LOC sau khi sửa

Sửa:

- `.env.example` — 76 LOC
- `README.md` — 210 LOC
- `src/cuti/cli.py` — 82 LOC
- `src/cuti/cli_parser.py` — 63 LOC
- `src/cuti/config.py` — 248 LOC
- `src/cuti/config_types.py` — 71 LOC
- `src/cuti/pipeline/report.py` — 234 LOC
- `NOTION_SANDBOX/PROVENANCE.json` — 11 LOC
- `notion.md` — 63 LOC

Thêm:

- `src/cuti/pipeline/details.py` — 54 LOC
- `tests/test_live_details.py` — 119 LOC

Xoá: không có.

Diff schema: không đổi bảng, cột hoặc index; `src/cuti/storage/schema_ddl.py` không bị sửa.

## 4. Từng task được giao

- T1: thêm duy nhất `build_lot_url(base_url, lot_id)` để dựng URL public lot từ `CUTI_CATAWIKI_API_BASE`; có test offline trực tiếp.
- T2: thêm env `CUTI_DETAILS_ENABLED=false`, `CUTI_DETAILS_REQUEST_DELAY_SECONDS=1.0`, `CUTI_DETAILS_MAX_RETRIES=2`; khai báo trong `SETTING_SPECS`, `Settings` và `.env.example`. Retry chỉ timeout, HTTP 429 hoặc 500–599, backoff nhân đôi.
- T3: khi Details tắt, `settle_lots`/`ingest_one_lot` không truyền fetcher và không gọi HTTP; verify vẫn offline.
- T4: thêm `cuti fetch-lot-details --url <url>` hoặc `--lot-id <id>`, chỉ fetch/parse một trang, in JSON, không mở hoặc ghi SQLite; README có hướng dẫn smoke test tay.
- T5: test fake-fetcher không mạng cho URL, delay/retry, lỗi vĩnh viễn vẫn persist lot, flag tắt không fetch và flag bật lưu typed fields, `model_key_tier`, `lot_desc`.

## 5. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Không có câu hỏi mới. Không thêm dependency/client HTTP, không sửa `pricing.py`, `config/rules.json` hoặc DDL.
- GNU Make/WSL không được cài trên máy đóng gói nên không chạy được literal `make verify`; thân verify chạy xanh như mục 2. Sandbox có GNU Make cần chạy lại literal `make verify`.
- Khi bật Details, chỉ lỗi transport tạm thời/vĩnh viễn trả `None` để lot vẫn lưu; lỗi parser dữ liệu không bị nuốt.
- Quy ước hash: source commit ở mục 1 chứa mã/test; commit tài liệu sau đó không thể tự tham chiếu chính hash của nó mà không làm thay đổi hash.
