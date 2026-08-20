# Bàn giao vòng 10 — Tầng 1 xanh; Tầng 2 chờ HTML người tải

## 1. Commit hash + ngày đóng gói

- Source commit: `5e482667b18f6291128b287f4f01ecae14bffa9a`.
- Ngày đóng gói: 2026-08-20 (Asia/Bangkok).
- `NOTION_SANDBOX/PROVENANCE.json` dùng cùng source commit và kết quả 286 test.

## 2. Output verify thật, nguyên văn

### Tầng 1 — verify offline

- Raw log: `var/verify/2026-08-20/verify.log`; dòng 1 là lệnh thực tế, dòng 351 là `Ran 286 tests`, dòng 558 là `SRC_LOC_MAX=230`, dòng 560 là `EXIT=0`.
- Log chứa stdout/stderr của toàn bộ test và workflow mẫu nguyên trạng; không có dòng ghép tay trong mục này.

### Tầng 2 — verify-live

- Lần live trước: `var/live/2026-08-20/verify-live.log`; dòng 1 là lệnh, dòng 87 là `EXIT=1`.
- Request `106019970`: `var/live/2026-08-20/fetch-lots.log`; dòng 51 ghi HTTP 403 và 392 byte, raw response ở dòng 52–63, dòng 98 là `EXIT=1`.
- `105924279`, `105418344`, `105809071`: không có request trong raw log vì fetch dừng tại 403 đầu tiên. Vòng này không thử lại bằng user-agent hoặc proxy khác.
- Không có HTML thật trong `tests/fixtures/live/` tại thời điểm đóng gói. Vì không có fixture/browser input mới và listing source cũ đã 403, không chạy live lại; do đó chưa có raw log pipeline Round 10 mới.

## 3. File thêm / sửa / xoá, kèm LOC sau khi sửa

Sửa:

- `README.md` — 214 LOC (gỡ tham chiếu `mermaid.md`).
- `scripts/verify.py` — 147 LOC.
- `scripts/verify_live.py` — 393 LOC.
- `src/cuti/cli_commands.py` — 127 LOC.
- `src/cuti/cli_parser.py` — 77 LOC.
- `src/cuti/pipeline/ingest.py` — 116 LOC.
- `tests/test_pipeline_cli.py` — 355 LOC.
- `NOTION_SANDBOX/PROVENANCE.json` — 11 LOC.
- `notion.md` — cập nhật lúc đóng gói.

Thêm:

- `tests/test_live_lot_fixtures.py` — 42 LOC.
- `tests/test_verify_scripts.py` — 42 LOC.
- `var/verify/2026-08-20/verify.log` — 560 LOC, raw log tự sinh.

Xoá:

- `mermaid.md` — 298 LOC.

Diff schema: không đổi bảng, cột hoặc index; `src/cuti/storage/schema_ddl.py` không bị sửa.

## 4. Từng task được giao

- T1: thêm test offline chỉ đọc các file HTML thật đang có. Test không tạo fixture giả, không skip; thư mục hiện trống nên test không có case fixture để chạy. Khi người dùng đặt bốn file đã nêu, cùng test sẽ kiểm brand, ref/case code, caliber (trừ Rolex được chỉ định `None`), movement và description; các expectation `7T12`/`0AT0`, `503`, `500`, `None`/`16234(Y)` đã có. Không kiểm sold/hammer từ HTML; chưa có payload bidding thật nên chưa có fixture JSON `parse_bidding_block`.
- T2: thêm `cuti ingest --max-lots N`, mặc định `None` để giữ crawl 384 lot. Cap nằm trong `ingest_lots` trước `upsert_lots`; test xác nhận `10` ghi đúng 10, không flag vẫn 384, `0` và âm trả `ConfigError` qua CLI exit 1.
- T3: `verify-live` chạy pipeline tiếp sau fetch thất bại: `init-db`, `ingest --max-lots 50`, `settle` với `CUTI_DETAILS_ENABLED=true`, rồi `evaluate`, `liquidity`, `report`, `status` dạng JSON. Thiếu source env vẫn exit 0 và không network. Kết quả live mới chưa có vì chưa có nguồn listing hợp lệ sau 403 cũ.
- T4: `scripts/verify.py` tự sinh raw log ngày chạy với command, phiên bản Python, package, tên biến `CUTI_*`, toàn bộ output và `EXIT` cuối log; tự in giá trị LOC thật `SRC_LOC_MAX=230`. Tầng 1 đã chạy offline xanh 286 test. Tầng 2 giữ raw logs vòng trước và không được chỉnh/tóm tắt lại.
- T5: đã xoá `mermaid.md` và gỡ tham chiếu khỏi README. Không có tham chiếu Mermaid trong nội dung `AGENTS.md` hiện hữu để gỡ; file `AGENTS.md` có thay đổi độc lập của người dùng nên không đưa vào commit này.

## 5. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Tầng 2 chưa đóng: cần người dùng đặt HTML đã tải bằng trình duyệt tại `tests/fixtures/live/106019970.html`, `105924279.html`, `105418344.html`, `105809071.html`. Không có fixture giả trong zip.
- Sold/hammer không thuộc contract `parse_lot_page`; chỉ bổ sung test giá búa/trạng thái khi có payload bidding thật riêng cho `parse_bidding_block`.
- Catawiki 403 cũ được giữ nguyên trong raw log. Không thử lại bằng user-agent hoặc proxy khác. Để có pipeline T3 thật cần `CUTI_LOTS_SOURCE_URL` cho phép fetch; không tinh chỉnh code để làm số liệu trông đẹp.
- Không thêm dependency/env, không sửa `pricing.py`, DDL hay `config/rules.json`. Mọi file `src/cuti` hiện tối đa 230 dòng. Máy đóng gói không có GNU Make; lệnh đã chạy là thân lệnh Python project-local của `make verify`.
