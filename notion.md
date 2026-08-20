# Bàn giao vòng 9-live — CHƯA ĐÓNG: Catawiki chặn 403

## 1. Commit hash + ngày đóng gói

- Source commit: `bfcf1d0665f6e85636ec6e3a186bb9d92823013d`
- Ngày đóng gói: 2026-08-20 (Asia/Bangkok)
- `NOTION_SANDBOX/PROVENANCE.json` ghi cùng source commit và trạng thái live bị chặn.

## 2. Output verify thật, nguyên văn

Máy Windows này không có GNU `make`; đã chạy trực tiếp thân lệnh `verify` bằng Python project-local, offline và không cài package:

```text
> D:\\Projects\\cuti-tools\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v

----------------------------------------------------------------------
Ran 281 tests in 8.918s

OK

VERIFY OK — artifacts: D:\\Projects\\cuti-tools\\var\\verify\\7d64717c1ff4
VERIFY_EXIT=0
SRC_LOC_MAX=230_OK
```

Kết quả tầng 1: 281 passed, 0 failed, 0 skipped. `scripts/verify.py` là thân lệnh của target `make verify` và chạy offline.

### Tầng 2 — verify-live

- Lệnh `D:\\Projects\\cuti-tools\\.venv\\Scripts\\python.exe scripts\\verify_live.py` đã chạy, thất bại exit `1`: [var/live/2026-08-20/verify-live.log](var/live/2026-08-20/verify-live.log), dòng 1 là lệnh, dòng 87 là `EXIT=1`.
- Lot `106019970`: HTTP `403`, `392` byte: [var/live/2026-08-20/fetch-lots.log](var/live/2026-08-20/fetch-lots.log), dòng 51; raw response nguyên văn ở dòng 52–63; exit ở dòng 98.
- Lot `105924279`, `105418344`, `105809071`: không có HTTP status/byte vì script dừng ngay sau 403 lot đầu theo T2.
- T4 (`ingest`, `evaluate`, `liquidity`, `report`, `status`): không chạy vì T2 phải dừng ngay khi 403; không có raw log T4 hay số liệu DB thật.

## 3. File thêm / sửa / xoá, kèm LOC sau khi sửa

Sửa:

- `Makefile` — 25 LOC
- `src/cuti/config.py` — 97 LOC
- `src/cuti/pipeline/report.py` — 230 LOC
- `src/cuti/pipeline/settlement_resolver.py` — 228 LOC
- `NOTION_SANDBOX/PROVENANCE.json` — 11 LOC
- `notion.md` — 73 LOC

Thêm:

- `scripts/verify_live.py` — 390 LOC
- `src/cuti/config_specs.py` — 163 LOC
- `src/cuti/pipeline/settlement_resolver_keys.py` — 29 LOC
- `tests/test_verify_live.py` — 32 LOC
- `var/live/2026-08-20/fetch-lots.log` — 98 LOC, raw log tự sinh
- `var/live/2026-08-20/verify-live.log` — 87 LOC, raw log tự sinh

Xoá: không có.

Diff schema: không đổi bảng, cột hoặc index; `src/cuti/storage/schema_ddl.py` không bị sửa.

## 4. Từng task được giao

- T1: thêm `scripts/verify_live.py` và target `make verify-live`; thiếu `CUTI_LOTS_SOURCE_URL` hoặc `CUTI_CATAWIKI_API_BASE` sẽ in rõ tên biến thiếu và exit 0. Cổng offline không gọi network.
- T2: script có đúng 4 lot (dưới trần 5), delay tối thiểu 1 giây, retry tối đa 2 cho timeout/429/5xx, telemetry URL/status/bytes/ms. Lần chạy thật bị HTTP 403 ngay `106019970`; response được giữ nguyên trong raw log và script dừng, không đổi user-agent/proxy.
- T3: chưa làm được vì không có HTML lot thật sau 403. Không tạo fixture hay test giả. `parse_lot_page` hiện không có field sold/hammer; hai giá trị này thuộc `catawiki_api.parse_bidding_block`, cần quyết định nguồn fixture/assertion trước khi thêm test.
- T4: chưa chạy vì T2 yêu cầu dừng ngay khi bị 403. Ngoài ra `ingest` hiện không có cap theo số lot và không fetch Details; không tự thêm hành vi đó ngoài prompt.
- T5: raw log tự sinh đã force-add và commit; có command, Python/package, tên CUTI env, telemetry request và `EXIT` cuối file. Tầng 2 thất bại nên vòng không đóng.
- Trần LOC mới: tách cơ học config và settlement resolver; mọi file trong `src/cuti` hiện không vượt 230 LOC, không đổi public API/default/schema.

## 5. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Cần cung cấp cách truy cập Catawiki được nguồn cho phép hoặc bốn HTML đã tải hợp lệ. Prompt cấm đổi user-agent/proxy để lách, nên không có bước thử nào khác sau 403.
- T3 yêu cầu sold/hammer trong test `parse_lot_page`, nhưng `LotDetails` không mang hai field này. Cần duyệt một trong: fixture JSON bidding riêng và test `parse_bidding_block`, hoặc thay đổi contract parser (không tự thực hiện).
- T4 đòi `ingest` giới hạn 50 lot và fetch Details; hai khả năng này không tồn tại trên lệnh `ingest` hiện tại. Cần duyệt thay đổi hành vi/CLI nếu vẫn muốn T4 đúng chữ.
- Không thêm dependency/env, không sửa DDL, `config/rules.json` hay `pricing.py`. GNU Make/WSL không có trên máy đóng gói; target đã tồn tại nhưng các lệnh thực tế ghi ở trên chạy bằng Python project-local.
