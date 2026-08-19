# Bàn giao refactor giới hạn LOC

## 1. Commit hash + ngày đóng gói

- Source commit: `511ea5ed4af879368e6f22ccd9447f7fc3e10d12`
- Ngày đóng gói: 2026-08-19 (Asia/Bangkok)
- `NOTION_SANDBOX/PROVENANCE.json` ghi cùng source commit.

## 2. Output verify thật, nguyên văn

Máy Windows này không có GNU `make` (lệnh `make verify` báo `make: The term 'make' is not recognized`). Đã chạy trực tiếp đúng thân lệnh `verify` bằng Python project-local, offline và không cài package:

```text
> D:\Projects\cuti-tools\.venv\Scripts\python.exe -m unittest discover -s tests -v

----------------------------------------------------------------------
Ran 251 tests in 9.731s

OK

VERIFY OK — artifacts: D:\Projects\cuti-tools\var\verify\b803dbd42aef
exit code: 0
```

Kết quả: 251 passed, 0 failed, 0 skipped. `scripts/verify.py` là thân lệnh mà target `make verify` gọi sau bước kiểm tra/generate sample fixture.

## 3. File thêm / sửa / xoá, kèm LOC sau khi sửa

Sửa:

- `src/cuti/cli.py` — 73 LOC
- `src/cuti/config.py` — 240 LOC
- `src/cuti/scrapers/catawiki_api.py` — 96 LOC
- `NOTION_SANDBOX/PROVENANCE.json` — 11 LOC
- `notion.md` — 61 LOC

Thêm:

- `src/cuti/cli_commands.py` — 89 LOC
- `src/cuti/cli_output.py` — 13 LOC
- `src/cuti/cli_parser.py` — 58 LOC
- `src/cuti/config_types.py` — 68 LOC
- `src/cuti/scrapers/catawiki_payload.py` — 221 LOC
- `tests/test_source_line_limits.py` — 25 LOC

Xoá: không có.

Diff schema: không đổi bảng, cột hoặc index; `src/cuti/storage/schema_ddl.py` không bị sửa.

## 4. Từng task được giao

- T1: tách dataclass và parser payload JSON của Catawiki sang `catawiki_payload.py`; `CatawikiApi` chỉ giữ HTTP/phân trang. Các tên public cũ tiếp tục import từ `catawiki_api.py`.
- T2: tách dựng argparse, xuất JSON/text và điều phối subcommand; `cli.py` giữ `main`, `run`, `build_parser`, `_parse_day`, `_emit` và các patch point/import cũ.
- T3: tách các khai báo type/dataclass cấu hình dùng chung sang `config_types.py`, re-export từ `config.py`; không đổi env name, default hoặc validation.
- T4: thêm test quét đệ quy toàn bộ `src/cuti/**/*.py`, đếm mọi dòng vật lý (kể cả trống/comment) và fail khi vượt 250.

## 5. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Không có câu hỏi mới. Không thêm dependency/HTTP client/tính năng, không sửa `pricing.py`, `rules.json` hoặc DDL.
- GNU Make/WSL không được cài trên máy đóng gói, nên không thể chạy literal `make verify`; phần verify thực thi đã xanh như mục 2. Sandbox có GNU Make cần chạy lại `make verify` literal.
- Quy ước hash: source commit ở mục 1 chứa refactor/test; commit tài liệu/đóng gói sau đó không thể tự tham chiếu chính hash của nó mà không làm thay đổi hash.
