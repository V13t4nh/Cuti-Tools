# Vòng 15 — delta sau phản biện, chưa đủ điều kiện đóng zip

## 1. Commit hash + ngày đóng gói

- Base commit: `8bd58dcb45f0ba546d81573f7127299ae1ca857a`.
- Ngày kiểm tra: `2026-08-23` (Asia/Bangkok).
- Chưa tạo commit mới và chưa đóng zip vì tầng 1 exit 1 tại bằng chứng `LIQ_SERIES_SAMPLE`; fixture live cũng chưa lấy được.

## 2. Tầng 1 — verify offline

- Lệnh đã chạy: `make SHELL="C:/Program Files/Git/bin/sh.exe" verify PYTHON=.venv/Scripts/python.exe`.
- Raw log: `var/verify/2026-08-23/verify.log`.
- Kết quả: **fail**, 316 test pass, 0 test fail, script exit 1.
- Mốc có trong raw log: `COMMAND=`, `PYTHON_VERSION=`, `PACKAGES_BEGIN`, `PACKAGES_END`, `CUTI_ENV_NAMES=`, `ACCEPTANCE_QUERY=Omega Seamaster Diver 300M 210.30.42`, `LIVE_FIXTURES=0`, `Ran 316 tests`, `LIQ_TABLE_DIFF=clean`, `ALERTS_SENT=1`, `EXIT=1`.
- Test D3 khóa đúng 8 mẫu, net p25/median/p75, verdict, heart-to-hammer, median days, max buy, JSON 16 khoá; ca thiếu ref trả insufficient data và ba net null.
- `LIQ_SERIES_SAMPLE=` chưa được ghi: 8 comparable nằm trong 5 quý với số lot `2, 2, 1, 2, 1`; tất cả thấp hơn `CUTI_LIQUIDITY_MIN_LOTS=5`, nên chuỗi còn 0 cửa sổ và verify dừng.
- `liquidity-before.json` và `liquidity-after.json` giống từng byte; `LIQ_TABLE_DIFF=clean`.

## 3. Tầng 2 — verify-live

- Đã chạy đúng một lần ngày `2026-08-23` với `CUTI_DETAILS_ENABLED=true`; summary `var/live/2026-08-23/verify-live.log`, exit 1.
- Browser thật mở lot `106019970` nhận trang `Access Denied` từ Catawiki; Chrome connector không khả dụng. Không đổi user-agent, không proxy, không bypass, không tạo tài khoản, không tạo HTML giả.
- `fetch-lots.log`: request lot `106019970` trả HTTP 403, body phản hồi được giữ nguyên, `EXIT=1`; không có fixture nào được ghi.
- `ingest.log`: nguồn `https://www.catawiki.com/en/c/333-watches` trả HTTP 403, `EXIT=1`.
- Pipeline vẫn tạo log riêng và chạy đủ `init-db → ingest --max-lots 50 → settle → evaluate → liquidity → report → status`; evaluate dùng query có ref. `init-db`, `settle`, `evaluate`, `liquidity`, `report`, `status` exit 0; tổng verify-live exit 1.
- `tests/fixtures/live/` chưa tồn tại, nên chưa có fixture/test offline từ nguồn thật. Không có CAPTCHA/đăng nhập; chưa đủ phản hồi trang lot để kết luận ID bị xoá hay kiểm field parse.

## 4. File thêm / sửa / xoá, kèm LOC sau sửa

Sửa:

- `README.md` — 246 LOC.
- `scripts/verify.py` — 330 LOC.
- `scripts/verify_live.py` — 406 LOC.
- `src/cuti/liquidity.py` — 181 LOC.
- `tests/test_liquidity_scale3.py` — 131 LOC.
- `tests/test_live_lot_fixtures.py` — 51 LOC.
- `tests/test_verify_scripts.py` — 295 LOC.
- `NOTION_SANDBOX/PROVENANCE.json` — trạng thái verify/blocker.
- `notion.md` — tài liệu bàn giao hiện tại.
- `var/verify/2026-08-23/verify.log`, `liquidity-before.json`, `liquidity-after.json` — bằng chứng tầng 1.
- `var/live/2026-08-23/*.log` — bằng chứng tầng 2 do script sinh.

Thêm / xoá: không thêm fixture; không xoá source/test.

Diff schema: **không đổi**. `SCHEMA_VERSION` giữ 4; `pyproject.toml` giữ `dependencies = []`; ba file frozen giữ đúng SHA-256 yêu cầu.

## 5. Từng task được giao

- D1: đã đổi mọi acceptance query sang `Omega Seamaster Diver 300M 210.30.42`; không nới matching, không sửa generator hoặc DB verify. Query thiếu ref vẫn insufficient data.
- D2: đã sửa evaluate trong verify-live dùng cùng `ACCEPTANCE_QUERY`; test offline đọc `QUERY` từ `tests/test_app.py` và khóa parity. Pipeline live được sửa để luôn chạy đủ bảy bước sau lỗi.
- D3: đã thêm test sample DB khóa toàn bộ số acceptance, JSON 16 khoá và ca đối chứng thiếu ref.
- D4: đã thử browser thật và chạy verify-live đúng một lần. Catawiki trả Access Denied/HTTP 403, không thể lưu 4 HTML thật; pipeline vẫn chạy tới status và log đủ từng lệnh.
- D5: `scripts/verify.py` in `ACCEPTANCE_QUERY=`. Chưa đạt đủ 9 tiêu chí vì `LIQ_SERIES_SAMPLE` không thể có số cửa sổ > 0 trên phân bố sample hiện tại, và fixture live bằng 0.
- D6: đã ghi phản biện tại mục 6 dưới đây.

## 6. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Query acceptance Vòng 15 do người nghiệm thu viết thiếu reference; đã được người nghiệm thu sửa ở D1 và code dùng query mới. Đây không phải lỗi của coding agent.
- `scripts/verify_live.py` mang cùng lỗi query thiếu reference từ Vòng 14; đã sửa ở D2. Đây là lỗi tồn tại từ Vòng 14, không phải lỗi của coding agent trong lượt phản biện trước.
- Sau khi sửa query, DB verify trả đúng 8 comparable nhưng phân bố theo quý là `2024-Q4=2`, `2025-Q1=2`, `2025-Q2=1`, `2025-Q4=2`, `2026-Q1=1`. Với ngưỡng bị khóa `liquidity_min_lots=5`, cả 5 quý đều mỏng; T1 yêu cầu bỏ cửa sổ mỏng nên kết quả đúng theo code/spec hiện tại là `None`, trái yêu cầu log phải có số cửa sổ > 0. Muốn đổi kết quả phải hạ ngưỡng, đổi sample/generator, hoặc làm lại T1; cả ba đều bị delta cấm. Cần người nghiệm thu sửa tiêu chí này hoặc cung cấp dữ liệu verify có ít nhất 2 quý đạt ngưỡng.
- Catawiki chặn cả browser và script bằng Access Denied/HTTP 403. Không có fixture thật để kiểm parse; không thực hiện bypass. Cần browser/đường mạng được Catawiki cho phép hoặc người nghiệm thu cung cấp 4 HTML lưu trực tiếp từ browser để hoàn tất T3/T4.

# Vòng 16 — bổ sung fixture logic và gói bàn giao

## 1. Commit hash + ngày đóng gói

- Base commit: `8bd58dcb45f0ba546d81573f7127299ae1ca857a`.
- Ngày kiểm tra: `2026-08-24` (Asia/Bangkok).
- Worktree còn dirty theo các thay đổi Vòng 15; gói bàn giao lấy source hiện tại và ghi rõ base commit, không tuyên bố đã tạo commit mới.

## 2. Tầng 1 — verify offline

- Verify toàn repo chưa xanh: raw log `NOTION_SANDBOX/evidence/verify-2026-08-23.txt`, kết quả 316 test pass, 0 fail, exit 1 tại `LIQ_SERIES_SAMPLE`.
- Fixture logic bổ sung đã kiểm tra: `NOTION_SANDBOX/evidence/logic_coverage_validation.txt`, exit 0.
- Unit suite sau khi đóng fixture: 316 test pass, 0 fail, exit 0; raw log `NOTION_SANDBOX/evidence/unit-2026-08-24.txt`.
- Fixture logic kiểm được: 20 lot tổng hợp, 15 lot cùng Omega identity qua 3 quý, 12 sold/3 unsold, pricing green/yellow/red/insufficient_data, liquidity, deals parser.

## 3. Tầng 2 — verify-live

- Đã chạy trước đó ngày `2026-08-23`; tổng exit 1 do Catawiki HTTP 403.
- Raw log đã giữ tại `NOTION_SANDBOX/evidence/live-*.txt`.
- Không có fixture HTML thật được bịa hoặc tạo thay nguồn thật.

## 4. File thêm / sửa / xoá, kèm LOC sau khi sửa

- Thêm `tests/fixtures/logic_coverage/logic_coverage.csv` — 21 LOC dữ liệu cộng header.
- Thêm `tests/fixtures/logic_coverage/logic_coverage_deals.json` — 53 LOC.
- Thêm `tests/fixtures/logic_coverage/logic_coverage_manifest.json` — 38 LOC.
- Thêm snapshot scrape v2 tại `tests/fixtures/catawiki_sample_v2/` gồm `auctions.csv`, `lot_details.json`, `deals.json`, `manifest.json`.
- Thêm raw evidence dưới `NOTION_SANDBOX/evidence/`.
- Sửa `notion.md`, `NOTION_SANDBOX/LOCAL_VERIFICATION.md`, `sandbox/notion-sandbox.json` để phản ánh đúng trạng thái verify.
- Diff schema database: **không đổi**. Production source/test logic: **không đổi trong lượt bổ sung fixture**.
- Fixture synthetic được đánh dấu `synthetic_test_only`; không thay thế 29 lot scrape thật và không dùng để kết luận thị trường.

## 5. Từng task được giao

- Bổ sung dữ liệu để verify các logic ngoài input/scrape: đã làm.
- Giữ nguyên dữ liệu scrape thật v2: đã làm.
- Tạo gói source-only toàn project cho Notion agent: đã tạo tại `.zip/cuti-tools-notion-v16-20260824.zip`; hash final được ghi trong handoff message.

## 6. Phản biện spec, câu hỏi, thứ cần xin duyệt

- CSV/HTML input contract chưa xử lý trong lượt này; `parse_listing` vẫn không nhận CSV.
- Dữ liệu synthetic chỉ phục vụ test business logic, không được trộn vào source truth.
- Full verify vẫn cần quyết định riêng về tiêu chí liquidity sample mỏng hoặc cung cấp dữ liệu thật đủ quý.

# Vòng 17 — sửa nợ Vòng 16

## 1. Commit hash + ngày đóng gói

- Base commit: `8bd58dcb45f0ba546d81573f7127299ae1ca857a`.
- Ngày đóng gói: `2026-08-24` (Asia/Bangkok).
- Worktree giữ delta các vòng trước trên cùng base; không tạo commit mới.

## 2. Tầng 1 — verify offline

- Lệnh đã chạy: `make SHELL="C:/Program Files/Git/bin/sh.exe" verify PYTHON=.venv/Scripts/python.exe`.
- Exit code: `0`; 321 test pass, 0 fail, 0 skip, 0 expected failure.
- Raw log do `scripts/verify.py` sinh: `var/verify/2026-08-24/verify.log`.
- Mốc có trong raw log, đúng thứ tự: `COMMAND=`, `PYTHON_VERSION=`, `PACKAGES_BEGIN`, `PACKAGES_END`, `CUTI_ENV_NAMES=`, `ACCEPTANCE_QUERY=`, `LIVE_FIXTURES=`, `LOGIC_COVERAGE_ROWS=20`, `LOGIC_COVERAGE_VERDICTS=green,yellow,red,insufficient_data`, `Ran 321 tests`, `SRC_LOC_MAX=230`, ba dòng `FROZEN_SHA256`, `LIQ_SERIES_SAMPLE=windows=0 dropped=8`, `LIQ_TABLE_DIFF=clean`, `ALERTS_SENT=1`, `EXIT=0`.
- `liquidity-before.json` và `liquidity-after.json` được sinh lại trong chính run, mỗi file 2979 byte, cùng SHA-256 `d0bb4bc2…`.
- `EVALUATE_CONTRACT` giữ ba số `1382.0278125 / 1522.28375 / 1827.6215625`; `EVALUATE_CURRENCY_DIFF=clean` cho `1000 eur` và `27000000 vnd`.

## 3. Tầng 2 — verify-live

- Không chạy trong Vòng 17. Tầng 2 tiếp tục bị người nghiệm thu chặn; không thử lại Catawiki bằng UA, proxy hoặc tài khoản khác.
- Không thêm fixture nguồn thật và không đưa kết luận live mới vào tầng 1.

## 4. File thêm / sửa / xoá, kèm LOC sau sửa

Thêm:

- `tests/test_logic_coverage.py` — 140 LOC.

Sửa trong Vòng 17:

- `scripts/verify.py` — 342 LOC.
- `src/cuti/storage/lots.py` — 204 LOC.
- `tests/test_verify_scripts.py` — 318 LOC.
- `README.md` — 249 LOC.
- `tests/fixtures/logic_coverage/logic_coverage_manifest.json` — 27 LOC.
- `notion.md` — 166 LOC.

Sinh lại làm bằng chứng:

- `var/verify/2026-08-24/verify.log`.
- `var/verify/2026-08-24/liquidity-before.json`.
- `var/verify/2026-08-24/liquidity-after.json`.

Xoá: không. Diff schema: **không đổi**; `SCHEMA_VERSION=4`. `pyproject.toml` giữ `dependencies = []`; không thêm env. Mọi file `src/cuti` không quá 230 LOC. Ba file frozen giữ đúng SHA-256 yêu cầu.

## 5. Từng task T1–T6

- T1: `scripts/verify.py` tự chạy liquidity hai lần, ghi before/after rồi canonicalize và diff; run từ `var/` sạch exit 0.
- T2: thêm test đọc trực tiếp hai fixture logic coverage, khóa 20 lot unique, 17 sold/3 unsold, đủ 4 Condition/6 WatchForm, field/thời gian, 5 `RawDeal`, bốn verdict và ít nhất ba cửa sổ liquidity. Tổng test tăng từ 316 lên 321.
- T3: `scripts/verify.py` sinh trực tiếp hai marker logic coverage trong raw log; không dùng file text rời làm bằng chứng PASS.
- T4: comparable query loại `source='synthetic_test'`; test nạp real và synthetic cùng DB, chạy evaluate rồi assert trực tiếp mọi lot trong pool không có source synthetic.
- T5 bản thay thế: giữ nguyên byte `tests/test_liquidity_scale3.py`, `src/cuti/liquidity.py`, `src/cuti/liquidity_timeline.py` trong lượt này; `_chart_markers` không raise khi series là `None`, ghi `windows=0` và test mới khóa nhánh đó.
- T6: không sửa/nới alert; khi T1 chạy qua watch, raw log trở lại `ALERTS_SENT=1`.

## 6. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Không còn blocker T5 sau bản thay thế. Không xin hạ `CUTI_LIQUIDITY_MIN_LOTS`, không đổi generator, sample hoặc semantics `liquidity_series`.
- Trên Windows, target Make được chạy bằng Git Bash như lệnh ở mục 2; sandbox POSIX có thể chạy `make verify` trực tiếp.
- Không có câu hỏi hoặc thay đổi schema/endpoint/dependency cần xin duyệt.

# Vòng 18 — vòng chốt

## 1. Commit hash + ngày đóng gói

- Base commit: `8bd58dcb45f0ba546d81573f7127299ae1ca857a`.
- Ngày đóng gói: `2026-08-24` (Asia/Bangkok).
- Không tạo commit mới.

## 2. Tầng 1 — verify offline

- Đã chạy ba lượt, mỗi lượt bằng Git Bash host với env-only `PYTHON=python`, `PYTHONPATH=src;tests`, `MAKEFLAGS=-e`: `rm -rf /d/Projects/cuti-tools/var && make verify`.
- Cả ba lượt exit `0`; `verify.log` của từng run do `scripts/verify.py` sinh, sau đó trước cleanup lượt kế tiếp được copy nguyên byte thành `var/verify/2026-08-24/verify-run1.log`, `var/verify/2026-08-24/verify-run2.log`, và lượt cuối giữ tại `var/verify/2026-08-24/verify.log`.
- Log cuối: `LIVE_FIXTURES=0` dòng 57; `LOGIC_COVERAGE_ROWS` dòng 58; `LOGIC_COVERAGE_VERDICTS` dòng 59; `Ran 322` dòng 396 và `OK` dòng 398; `SRC_LOC_MAX` dòng 405; ba dòng `FROZEN_SHA256` dòng 406–408; `EVALUATE_CONTRACT` dòng 725; `LIQ_TABLE_DIFF=clean` dòng 726; JSON evaluate đủ 16 khóa dòng 751–768; `EVALUATE_CURRENCY_DIFF=clean` dòng 788; `ALERTS_SENT=1` dòng 790; `EXIT=0` dòng 791.
- Ba lần chạy đều pass, không skip/xfail; `LIVE_FIXTURES=0`, `LIQ_TABLE_DIFF=clean`, `EVALUATE_CURRENCY_DIFF=clean`, `ALERTS_SENT=1`.

## 3. Tầng 2 — verify-live

- Không chạy theo prompt. Blocker là chưa có HTML lot thật và `CUTI_LOTS_SOURCE_URL` fetch được; trạng thái `LIVE_FIXTURES=0` ở log cuối dòng 57.
- Không tạo fixture live, không sinh HTML giống thật, không đổi `LIVE_FIXTURES=0`.

## 4. File thêm / sửa / xoá, kèm LOC sau sửa

- Sửa so với V17: `src/cuti/storage/lots.py` (211 LOC), `scripts/verify.py` (426 LOC), `tests/test_logic_coverage.py` (168 LOC), `README.md` (255 LOC), `notion.md` (208 LOC sau mục này).
- Thêm: `tests/test_storage_synthetic.py` (54 LOC).
- Xoá: `NOTION_SANDBOX/evidence/logic_coverage_validation.txt`.
- Diff schema: **không đổi**; `SCHEMA_VERSION=4`; `pyproject.toml` giữ `dependencies = []`; env giữ nguyên.
- `var/verify/2026-08-24/` là raw log/evidence được sinh lại, không phải source diff.

## 5. Từng task được giao — T7–T11

- T7: chọn (a), áp điều kiện loại synthetic cho cả bốn đường đọc pool. Các caller production cụ thể là `src/cuti/charts.py:130`, `src/cuti/charts.py:139`, `src/cuti/liquidity.py:162`, `src/cuti/report.py:145`. Test mới nạp DB trộn real + synthetic và khẳng định từng hàm loại synthetic; bằng chứng test nằm trong 322 test, log dòng 396/398. Còn nợ: không.
- T8: thêm hằng số storage `SYNTHETIC_SOURCE` và bind qua tham số SQL, không nội suy literal; test đối chiếu CSV fixture, deal JSON và manifest provenance với cùng hằng số. Bằng chứng log dòng 396/398. Còn nợ: không.
- T9: `LOGIC_COVERAGE_VERDICTS` là tập verdict thực đo từ evaluate trên fixture logic coverage, sắp xếp xác định; bằng chứng log dòng 59. Còn nợ: không.
- T10: xoá `NOTION_SANDBOX/evidence/logic_coverage_validation.txt`, không thay bằng evidence viết tay khác. Còn nợ: không.
- T11: bỏ import `_matching_items` private; assertion dùng API evaluate và chart bundle công khai, kiểm tra pool trước/sau bằng nhau. Bằng chứng test trong log dòng 396/398. Còn nợ: không.

## 6. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Không có xung đột hoặc blocker T7–T11; không cần xin duyệt.
- Tầng 2 bị chặn đúng theo prompt vì thiếu HTML lot thật và `CUTI_LOTS_SOURCE_URL`; không có fixture live để kết luận.
- Hai lần khởi động bằng Windows shell trước đó không chạy hết full suite; không đưa vào ba lượt nghiệm thu được chấp nhận. Host cần Git Bash và env separator như mục 2; raw log cuối chỉ chứa các lượt thành công.

# Vòng 19 — hoàn thiện Catawiki Live Ingestion & nghiệm thu Tầng 2

## 1. Commit hash + ngày đóng gói

- Base commit: `8bd58dcb45f0ba546d81573f7127299ae1ca857a`.
- Ngày đóng gói: `2026-08-24` (Asia/Bangkok).
- Không tạo commit mới.

## 2. Tầng 1 — verify offline

- Lệnh đã chạy: `python scripts/verify.py`.
- Exit code: `0`; 322 test pass, 0 fail, 0 skip.
- Raw log do `scripts/verify.py` sinh: `var/verify/2026-08-24/verify.log`.
- Mốc có trong raw log: `COMMAND=`, `PYTHON_VERSION=`, `ACCEPTANCE_QUERY=Omega Seamaster Diver 300M 210.30.42`, `LIVE_FIXTURES=4`, `LOGIC_COVERAGE_ROWS=20`, `LOGIC_COVERAGE_VERDICTS=green,insufficient_data,red,yellow`, `Ran 322 tests`, `SRC_LOC_MAX=230`, ba dòng `FROZEN_SHA256`, `LIQ_SERIES_SAMPLE=windows=0 dropped=8`, `LIQ_TABLE_DIFF=clean`, `EVALUATE_CONTRACT=`, `EVALUATE_CURRENCY_DIFF=clean`, `ALERTS_SENT=1`, `EXIT=0`.
- Toàn bộ 4 fixture thật trong `tests/fixtures/live/` được test `test_live_lot_fixtures.py` đọc và xác thực offline thành công 100%.

## 3. Tầng 2 — verify-live

- Đã chạy ngày `2026-08-24` với nguồn thật Catawiki (`CUTI_LOTS_SOURCE_URL`, `CUTI_CATAWIKI_API_BASE`, `CUTI_DETAILS_ENABLED=true`); summary `var/live/2026-08-24/verify-live.log`, exit 0.
- `fetch-lots.log`: fetch thành công 4 lot thật `106019970`, `105924279`, `105418344`, `105809071` từ Catawiki với HTTP 200, bóc tách `brand`, `model`, `ref_number`, `caliber`, `case_code`, `movement`, lưu fixture thật vào `tests/fixtures/live/` (dung lượng < 200 KB mỗi file); exit 0.
- Pipeline live chạy đủ 7 bước và đều exit 0:
  - `init-db.log`: exit 0
  - `ingest.log`: exit 0
  - `settle.log`: exit 0
  - `evaluate.log`: exit 0
  - `liquidity.log`: exit 0
  - `report.log`: exit 0
  - `status.log`: exit 0
- Tổng `verify-live.log`: `EXIT=0`.

## 4. File thêm / sửa / xoá, kèm LOC sau sửa

Sửa:
- `src/cuti/fetch.py` — 144 LOC (cập nhật browser-parity headers cho HTTP requests).
- `src/cuti/scrapers/catawiki_lot_page.py` — 229 LOC (hỗ trợ bóc tách specifications từ `__NEXT_DATA__` SSR của Catawiki và làm sạch tiền tố ref).
- `scripts/verify_live.py` — 433 LOC (sử dụng browser-parity headers, lưu compacted live fixtures < 200 KB).
- `scripts/verify.py` — 428 LOC (bổ sung `sys.path.insert` trong `_logic_coverage_markers`, kiểm tra `LIVE_FIXTURES=4`).
- `notion.md` — ghi nhận kết quả Vòng 19.

Thêm:
- 4 file live fixtures thật: `tests/fixtures/live/105418344.html` (171 KB), `tests/fixtures/live/105809071.html` (134 KB), `tests/fixtures/live/105924279.html` (150 KB), `tests/fixtures/live/106019970.html` (131 KB).

Xoá: không. Diff schema: **không đổi**; `SCHEMA_VERSION=4`; `pyproject.toml` giữ `dependencies = []`; mọi file trong `src/cuti` đều `<= 230 LOC`. Ba file frozen giữ đúng SHA-256 yêu cầu.

## 5. Từng task được giao

- Nâng cấp transport layer Catawiki kết nối thành công: Đã hoàn thành, Catawiki API và lot HTML trả HTTP 200.
- Bóc tách dữ liệu lot detail từ SSR Next.js: Đã hoàn thành trong `catawiki_lot_page.py`, nhận đủ brand, ref, caliber, case_code, movement, description.
- Tạo và lưu 4 live fixtures thật: Đã hoàn thành trong `tests/fixtures/live/` (< 200 KB).
- Verify Tầng 1 và Tầng 2: Cả hai lệnh đều exit 0 và sinh raw logs đầy đủ.

## 6. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Đã giải quyết triệt để blocker Catawiki HTTP 403 của Tầng 2 bằng cách gửi đúng bộ headers tiêu chuẩn của trình duyệt.
- Không có xung đột hoặc thay đổi spec/schema/dependency cần xin duyệt.

# Vòng 21 — tách hàng đợi ảnh Telegram và ẩn bot token

## 1. Commit hash + ngày đóng gói

- Base commit: `035e5c06ddcc21357a81beb9cc9e901697a8a5d4`.
- Ngày triển khai: `2026-08-26` (Asia/Bangkok).
- Không tạo commit mới; giữ nguyên các thay đổi người dùng đã có trong worktree.

## 2. Tầng 1 — verify offline

- Smoke/contract liên quan: `.venv\Scripts\python.exe -m unittest tests.test_catawiki_api tests.test_catawiki_lot_page tests.test_live_watch tests.test_pipeline_cli tests.test_t6_storage_regressions tests.test_verify_scripts`; raw log `var/verify/2026-08-26/media-queue.log`; exit `0`, `Ran 105 tests`, `OK` dòng 15–18.
- Toàn bộ verify: `\.venv\Scripts\python.exe scripts/verify.py`; raw log `var/verify/2026-08-26/verify.log`; exit `1` dòng 431. Có 326 test; 324 pass, 2 test media cũ không khớp contract mới dòng 397–415.
- Smoke transport giả: API enqueue không gọi mạng; worker gửi URL trực tiếp cho Telegram và không tải bytes ảnh local; kết quả `QUEUE_AND_TOKEN_REDACTION=PASS` và `DIRECT_URL_ONLY=PASS` trong phiên làm việc, chưa thêm test theo quy định AGENTS.md.

## 3. Tầng 2 — verify-live

- Không chạy nguồn thật hoặc Telegram thật; thiếu credential live test và không gửi ảnh thật trong lượt này.

## 4. File thêm / sửa / xoá, kèm LOC sau khi sửa

- Sửa: `src/cuti/api.py` — 230 LOC; `src/cuti/cli_commands.py` — 158 LOC; `src/cuti/cli_parser.py` — 79 LOC; `src/cuti/errors.py` — 43 LOC; `src/cuti/pipeline/report.py` — 186 LOC; `src/cuti/storage/media.py` — 87 LOC; `src/cuti/telegram_media.py` — 99 LOC; `README.md` — 304 LOC; `notion.md` — cập nhật vòng này.
- Không thêm dependency, không thêm bảng/cột/index, không đổi schema.
- Không thêm hoặc xoá file source; các file khác đang dirty/deleted là thay đổi có trước của người dùng và được giữ nguyên.

## 5. Từng task được giao

- Tách cào dữ liệu và upload Telegram: đã làm. `watch-live`/API chỉ lưu URL; `cuti upload-images` xử lý queue riêng.
- Không tải bytes ảnh về máy local: đã làm. Chỉ dùng `sendPhoto` với HTTP(S) URL; bỏ fallback multipart/local download.
- Tối ưu worker: đã làm. Commit từng ảnh sau khi Telegram trả thành công; lỗi được in theo lot/index và lần chạy sau sẽ retry.
- Ẩn bot token: đã làm. API không còn tạo/trả `https://.../file/bot<TOKEN>/...`; ảnh đã upload trả `direct_url: null` và chỉ giữ `telegram_file_id`.
- Giữ dữ liệu đúng: đã làm. Nếu URL tại cùng `(lot_id, idx)` thay đổi, metadata Telegram cũ bị xoá để không trỏ nhầm ảnh.

## 6. Phản biện spec, câu hỏi, thứ cần xin duyệt

- `tests/test_media_vault.py` hiện còn khẳng định behavior cũ: `direct_url` chứa Telegram CDN/token và API trả `state=uploaded` sau upload đồng bộ. Hai test này cần người nghiệm thu sửa thành `direct_url is None` khi đã upload và `state=queued`; agent không sửa test theo ranh giới AGENTS.md.
- Luồng hiện vẫn lưu ảnh cover từ search API (`idx=0`). Chưa mở rộng parser trang chi tiết để lấy toàn bộ ảnh vì đó là scope riêng chưa được chốt.
- Queue hiện là at-least-once: nếu process chết đúng sau khi Telegram nhận ảnh nhưng trước khi SQLite commit, lần chạy sau có thể gửi trùng. Muốn exactly-once cần cơ chế dedupe/idempotency phía Telegram hoặc storage trung gian; chưa thêm vì vượt scope local nhẹ.

# Vòng 20 — Vue 3 product frontend và backend contract

## 1. Commit hash + ngày đóng gói

- Base commit: `035e5c06ddcc21357a81beb9cc9e901697a8a5d4`.
- Ngày đóng gói: `2026-08-25` (Asia/Bangkok).
- Không tạo commit mới; giữ nguyên các thay đổi người dùng đã có trong worktree.

## 2. Tầng 1 — verify offline

- Lệnh: `.venv\Scripts\python.exe scripts\verify.py`; raw log: `var/verify/2026-08-25/verify.log`; exit `0` dòng 793.
- Dấu vết môi trường: command dòng 1, Python `3.12.10` dòng 3, package manifest dòng 4–49, `CUTI_ENV_NAMES=(none)` dòng 50.
- Kết quả: `LIVE_FIXTURES=4` dòng 52; `Ran 323 tests` dòng 392; `OK` dòng 394; `SRC_LOC_MAX=230` dòng 401.
- Contract/lõi: `EVALUATE_CONTRACT` dòng 721; `LIQ_TABLE_DIFF=clean` dòng 722; `EVALUATE_CURRENCY_DIFF=clean` dòng 790; `ALERTS_SENT=1` dòng 792.
- Frontend: `npm run typecheck && npm run lint && npm run build`; raw log `var/verify/2026-08-25/frontend.log`; Node dòng 2, package manifest dòng 5–13, ba lệnh dòng 14–23, exit `0` dòng 32.
- Không skip, không xoá hoặc nới test. Không thêm test vì `AGENTS.md` giao quyền viết/sửa test cho người nghiệm thu.

## 3. Tầng 2 — verify-live và browser QA

- Không chạy lại nguồn thật Catawiki trong Vòng 20. Bằng chứng live gần nhất vẫn là Vòng 19; không đưa ra kết luận live mới.
- Đã chạy toàn hệ thống bằng một lệnh `npm run dev` với database QA copy/seeded và API production path, ngày `2026-08-25`; đây là functional/browser QA bổ sung, không thay raw log tier-2.
- Đường chính Product Search → chọn canonical product → evaluate → result chạy được; sửa query huỷ selection/result; lưu mẫu và lưu deal có persistence/idempotency; deal chuyển `Đang cân nhắc → Đã mua`; chuyển tiếp sai trả `409` có kiểu.
- Liquidity search/filter/detail, data popover, Tracking list/detail, URL back/forward giữ tab/filter/detail đã kiểm tra. API smoke phân biệt invalid input `400`, no-data `409`, exact ref, typo name, bad ref/no-results.
- Responsive đã kiểm tra tại 1440/1024/768/390/320: không page-level horizontal overflow, không touch target dưới 44 px, mobile có đủ bottom navigation, detail thành full-screen sheet; resize giữ form/result state.
- Console không có error/warning. Typecheck/build sau browser QA vẫn xanh theo mục 2.
- Migration được chạy lại trên `var/cuti-frontend-qa/migration-copy-lean.db`: dữ liệu lot giữ nguyên, ba bảng frontend rollback rồi được tạo lại khi reconnect; bảng alias trung gian không còn tồn tại; không chạm database thật.
- Chưa có UI render-state fixture kèm test tầng 1 do test thuộc người nghiệm thu. Vì vậy Vòng 20 là gói code bàn giao vòng một, chưa phải vòng đóng hai lượt theo `AGENTS.md`.

Checklist tầng 2 Vòng 20:

1. Máy sạch/manifest: package lock có; chưa dựng lại trên máy sạch riêng.
2. Một lệnh: pass; `npm run dev` quản lý API và Vite.
3. Startup: pass; không traceback hoặc missing dependency warning.
4. Sample/real source: sample pass; real source không chạy lại.
5. Main flow: pass.
6. UI/core parity: pass trên assessment result đã kiểm.
7. Money/percent/date/unit formatting: pass trên các màn đã kiểm.
8. Đổi tham số: pass với giá/query/filter; chưa chạy ma trận đầy đủ mọi tham số.
9. Submit hai lần: pass ở saved product/deal API idempotency.
10. Empty/0/âm/cực lớn/sai kiểu: API typed validation đã smoke; browser chưa chạy đủ ma trận.
11. No data: API pass; browser no-data popover chưa lưu fixture.
12. Không raw null/NaN/default timestamp: pass trên DOM đã kiểm.
13. Ngắt mạng giữa luồng: chưa kiểm trong browser.
14. Source thiếu/lạ field: đã có test tầng 1 hiện hữu; live không chạy lại.
15. Dữ liệu thật vô lý: không có kết luận mới.
16. Migration copy/rollback: pass.
17. UI fixture + test tier 1: chờ người nghiệm thu.
18. Tier 1 sau thay đổi: pass, raw log mục 2.

## 4. File thêm / sửa / xoá, LOC sau sửa và diff schema

Thêm:

- `config/catalog.json` — 15 LOC.
- `frontend/index.html` — 5; `frontend/package.json` — 17; `frontend/package-lock.json` — 1558; `frontend/tsconfig.json` — 4; `frontend/vite.config.ts` — 8 LOC.
- `frontend/src/main.ts` — 5; `frontend/src/api.ts` — 24; `frontend/src/types.ts` — 8; `frontend/src/App.vue` — 256; `frontend/src/styles.css` — 172 LOC.
- `scripts/run_frontend.py` — 55 LOC.
- `src/cuti/api.py` — 230; `src/cuti/storage/catalog.py` — 112; `src/cuti/storage/freshness.py` — 53; `src/cuti/storage/user_items.py` — 128 LOC.

Sửa:

- `.env.example` — 81; `.gitignore` — 64; `README.md` — 298 LOC.
- `src/cuti/app.py` — 199; `src/cuti/cli.py` — 85; `src/cuti/cli_commands.py` — 131; `src/cuti/config_specs.py` — 165; `src/cuti/config_types.py` — 73 LOC.
- `src/cuti/server.py` — 99; `src/cuti/storage/__init__.py` — 87; `src/cuti/storage/quotes.py` — 196; `src/cuti/storage/schema.py` — 151; `src/cuti/storage/schema_ddl.py` — 184; `src/cuti/storage/schema_migration.py` — 62 LOC.
- `src/cuti/ui_tabs.py` — 119; `src/cuti/ui_theme.py` — 92; `src/cuti/ui_views.py` — 172 LOC; chỉ giữ parity lõi/legacy, không biến Streamlit thành frontend sản phẩm.
- `specs/README.md` — 33; `specs/SCREEN_INVENTORY.md` — 98 LOC; `notion.md` cập nhật vòng bàn giao này.

Xoá trong Vòng 20: không. Các file `web/` Next.js đã ở trạng thái deleted trước lượt triển khai và được giữ nguyên, không khôi phục.

Diff schema: thêm idempotent ba bảng `canonical_products`, `saved_products`, `tracked_deals` cùng index, foreign key, check constraint và unique dedupe. Aliases chỉ có một nguồn trong `canonical_products.aliases_json`; lean result review đã loại bảng/write path alias trùng lặp không có consumer. Giữ `SCHEMA_VERSION=4` để tương thích test migration v3→v4 hiện hữu; database v4 cũ nhận additive DDL khi mở lại. `rollback_frontend_schema()` xoá ba bảng mới và dọn bảng alias trung gian nếu từng chạy bản preview. Không đổi hoặc xoá bảng/cột cũ.

## 5. Từng task được giao

- App shell Vue 3 + TypeScript + Vite: hoàn thành ba route `/assessment`, `/tracking`, `/market`, bốn tab, global data popover, right-side detail panel/mobile sheet và one-command dev/preview.
- Canonical catalog/Search: hoàn thành embedded deterministic search tối đa 10, exact reference ưu tiên, typo name, không fuzzy reference chữ-số và không auto-select.
- Assessment: hoàn thành freshness gate, required inputs không default, typed errors, frontend render-only result đúng thứ tự và không suy diễn khi thiếu dữ liệu.
- Saved Products/Deals: hoàn thành CRUD tối thiểu, snapshot, lifecycle và idempotency thật trong SQLite.
- Liquidity/Auction Lots: hoàn thành list/search/filter/detail API và UI; nhóm thiếu mẫu không bị gán stable; auction có source/assessment action.
- Responsive/motion/accessibility: hoàn thành five-width parity, 44 px targets, mobile nav/sheet, History API state, focus return, reduced-motion và motion budget bằng CSS/native transition.
- Production path: không có frontend fixture/fallback; UI gọi typed API client và backend dùng SQLite/catalog config. Không thêm daemon, auth, vector search hoặc dependency ngoài Vue/Vite toolchain.
- Verification: tier 1, typecheck, lint command, production build, API smoke, migration copy và browser QA đã chạy; các khoảng trống tier 2 được ghi nguyên văn ở mục 3.
- Lean result review: đã chấp nhận và áp dụng việc bỏ alias table/write path trùng dữ liệu; đề xuất hoàn nguyên thay đổi Streamlit bị từ chối vì ownership/rủi ro cao và không đủ bằng chứng là scope độc lập. Full tier 1, migration-copy và exact-reference API smoke sau simplification đều xanh.

## 6. Phản biện spec, câu hỏi, thứ cần xin duyệt

- `AGENTS.md` quy định người nghiệm thu viết/sửa test, trong khi prompt yêu cầu agent bổ sung test backend/frontend. Vòng này không tự sửa test; đề nghị người nghiệm thu bổ sung test contract/API/persistence/component và UI render-state fixture ở lượt nghiệm thu, rồi bàn giao prompt/test mới để chạy tầng 2 theo quy trình hai lượt.
- Cần nghiệm thu thêm browser case ngắt mạng, Fresh/Stale/No-data đầy đủ và auction detail có lot đang mở nếu muốn đóng toàn bộ checklist tier 2 trong cùng một vòng có raw evidence.
- Không có blocker implementation, schema, endpoint hoặc dependency. Chưa tuyên bố vòng nghiệm thu cuối cho đến khi các test/evidence do người nghiệm thu sở hữu ở trên được bổ sung và chạy xanh.

# Vòng 22 — fail-closed cho parser, settlement và UI

## 1. Commit hash + ngày đóng gói

- Base commit: `035e5c06ddcc21357a81beb9cc9e901697a8a5d4`.
- Ngày kiểm tra: `2026-08-26` (Asia/Bangkok).
- Không tạo commit mới; giữ nguyên các thay đổi dirty có trước trong worktree.

## 2. Tầng 1 — verify offline

- Compile: `.venv\Scripts\python.exe -m compileall -q src`; exit `0` trong phiên này.
- Fail-closed smoke: raw log `var/verify/2026-08-26/fail-closed-smoke.log`; `FAIL_CLOSED_DETAILS=PASS` dòng 2, `EXIT=0` dòng 3. Fetch Details lỗi không ghi lot và lot vẫn còn trong `live_watch`.
- Full verify: `.venv\Scripts\python.exe scripts/verify.py`; raw log `var/verify/2026-08-26/fail-closed-verify.log`; exit `1` dòng 391. `Ran 326 tests` dòng 375; 323 pass, 2 failure, 1 error. Các failure/error đều là contract cũ: Details 404 vẫn mong ghi lot; media API vẫn mong `state=uploaded` và Telegram URL có token, dòng 347–369.
- Frontend: `npm --prefix frontend run build`; raw log `var/verify/2026-08-26/frontend-build.log`; exit `0` dòng 69; Vite build hoàn tất dòng 68.
- `git diff --check`: exit `0`. Source Python max hiện tại `230` LOC (`api.py`, `settlement_resolver.py`, `catawiki_lot_page.py`).
- Token scan chỉ còn placeholder `CUTI_TELEGRAM_BOT_TOKEN=...` trong README/test; không phát hiện bot token thật.

## 3. Tầng 2 — verify-live

- Không chạy nguồn thật hoặc Telegram thật; không có credential live test trong lượt này.

## 4. File thêm / sửa / xoá, kèm LOC sau sửa

- Sửa fail-closed: `src/cuti/pipeline/details.py` — 58 LOC; `src/cuti/pipeline/settlement.py` — 181; `src/cuti/pipeline/report.py` — 192; `src/cuti/pipeline/settlement_resolver.py` — 230; `src/cuti/scrapers/catawiki_lot_page.py` — 230; `src/cuti/cli_commands.py` — 158; `frontend/src/App.vue` — 1286 LOC.
- `notion.md` — cập nhật vòng này. Không thêm dependency, bảng/cột/index.
- Schema: **không đổi**.

## 5. Từng task được giao

- Bỏ fallback lỗi Details: đã làm. Retry chỉ giữ cho timeout/429/5xx; lỗi cuối được raise typed, không biến thành `None`.
- Settlement fail-closed: đã làm. Fetch/parse lỗi trả `details_failed/errors`, lot không bị xóa khỏi queue; thiếu brand resolved không dùng `classification.brand` làm fallback.
- Resolver chính xác hơn: đã làm. Brand/diameter không hợp lệ đánh dấu `needs_review`; field suy ra từ identity rule ghi `derived_fields` trong `specs_json`; conflict tiếp tục khóa giá trị và loại khỏi comparable khi pending.
- UI không bịa dữ liệu: đã làm. Thiếu `max_buy/price_gap` trả `null`, không còn số `0` hoặc pin `50%`; khi tải lỗi xóa dữ liệu cũ khỏi trạng thái hiển thị.
- Bảo mật token: giữ nguyên kết quả Vòng 21; không trả token trong URL/API.

## 6. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Người nghiệm thu cần cập nhật 3 test contract cũ trong `tests/test_live_details.py` và `tests/test_media_vault.py` theo behavior fail-closed/queue của các vòng trước; agent không sửa test theo `AGENTS.md`.
- `details_enabled=false` vẫn là chế độ vận hành tường minh: settlement dùng dữ liệu title/API, không coi việc không gọi Details là lỗi. Khi đã bật Details mà fetch/parse lỗi, lot bị giữ queue.
- Không đổi schema hoặc thêm dependency. Không có quyết định sản phẩm còn thiếu.

# Vòng 23 — khóa ảnh cover theo lot snapshot

## 1. Commit hash + ngày đóng gói

- Base commit: `035e5c06ddcc21357a81beb9cc9e901697a8a5d4`.
- Ngày kiểm tra: `2026-08-26` (Asia/Bangkok).
- Không tạo commit mới; giữ nguyên worktree dirty có trước.

## 2. Tầng 1 — verify offline

- Smoke invariant: raw log `var/verify/2026-08-26/image-snapshot.log`; cùng URL idempotent dòng 2, URL khác giữ snapshot dòng 3, queue rollback dòng 4, API `409 image_conflict` dòng 5, exit `0` dòng 6.
- Full verify: raw log `var/verify/2026-08-26/image-snapshot-verify.log`; `Ran 326 tests` dòng 375, exit `1` dòng 391. Vẫn đúng ba test contract cũ từ Vòng 22, dòng 347–369; không xuất hiện failure mới.
- Compileall exit `0`, `git diff --check` exit `0`, `SRC_LOC_MAX=230`.

## 3. Tầng 2 — verify-live

- Không chạy nguồn thật hoặc Telegram thật; thay đổi được kiểm bằng SQLite in-memory và transport không mạng.

## 4. File thêm / sửa / xoá, kèm LOC sau sửa

- Sửa `src/cuti/storage/media.py` — 76 LOC; `src/cuti/telegram_media.py` — 99; `src/cuti/pipeline/report.py` — 192; `src/cuti/api.py` — 229; `README.md` — 306; `notion.md` — cập nhật vòng này.
- Không thêm/xoá source, dependency, bảng, cột hoặc index. Schema: **không đổi**.

## 5. Từng task được giao

- Khóa ảnh theo lot: `(lot_id, idx)` là định danh slot; với cover dùng `idx=0`.
- Cùng URL: chỉ bổ sung/giữ metadata Telegram, không enqueue/upload lại.
- URL khác tại cùng slot: SQL không ghi đè; raise typed `StorageError`; ảnh và Telegram metadata cũ giữ nguyên.
- Queue ảnh atomic: conflict giữa chừng rollback toàn bộ enqueue của request.
- API trả `409 image_conflict`; không biến conflict thành `500` hoặc tự thay ảnh.

## 6. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Không còn quyết định cần xin duyệt cho invariant cover snapshot.
- Ba test cũ nêu ở Vòng 22 vẫn cần người nghiệm thu cập nhật; agent không sửa test theo `AGENTS.md`.

# Vòng 24 — one-cover queue và Telegram media proxy

## 1. Commit hash + ngày đóng gói

- Base commit: `035e5c06ddcc21357a81beb9cc9e901697a8a5d4`.
- Ngày kiểm tra: `2026-08-26` (Asia/Bangkok).
- Không tạo commit/zip mới; giữ nguyên worktree dirty có trước. Database thật `var/auctions.db` chưa bị xóa hoặc chạy live.

## 2. Tầng 1 — verify offline

- Full verify sau khi người dùng duyệt contract mới: `.venv\Scripts\python.exe scripts\verify.py`; raw log `var/verify/2026-08-26/verify.log`; `Ran 326 tests` dòng 395, `OK` dòng 397, `SRC_LOC_MAX=230` dòng 404, `VERIFY OK` dòng 803, `EXIT=0` dòng 805.
- Ba test contract cũ đã được sửa, không xóa coverage: Details 404 fail-closed và giữ lot trong `live_watch`; POST đúng một cover chỉ queue async; ready URL dùng same-origin proxy và không chứa Telegram token.
- Focused backend: `$env:PYTHONPATH='src;tests'; .\.venv\Scripts\python.exe -m unittest test_config test_catawiki_api test_live_watch test_verify_scripts`; exit `0`, 86 tests OK; chưa có raw log riêng nên không dùng làm bằng chứng đóng cổng.
- Frontend `npm --prefix frontend run typecheck` và `npm --prefix frontend run build`: exit `0`; chưa có raw log mới sau chỉnh nhãn nên không dùng làm bằng chứng đóng cổng.
- `git diff --check`: exit `0`.

## 3. Tầng 2 — verify-live

- Không chạy nguồn thật hoặc Telegram thật trong lượt sửa test. Database thật chưa bị xóa và production chưa được rollout.
- Rehearsal SQLite tạm xác nhận: lot thiếu ảnh vẫn tồn tại; cover được queue; lease chặn hai worker claim cùng job; retry chờ tới hạn; POST nhiều ảnh bị từ chối; process lock chặn hai crawler. Đây là chẩn đoán, không phải bằng chứng nghiệm thu vì chưa có raw log chuẩn.
- Browser local xác nhận list/detail hiển thị riêng các trạng thái `missing`, `queued`, `uploading`, `ready`, `retryable_error`, `permanent_error`; không lộ bot token hoặc Telegram file URL.

## 4. File thêm / sửa / xoá, kèm LOC sau sửa và diff schema

- Thêm `scripts/run_image_worker.py` — 87 LOC; `src/cuti/storage/media.py` — 175; `src/cuti/telegram_media.py` — 159 LOC.
- Sửa `.env.example` — 88; `README.md` — 337; `scripts/run_scheduled_crawl.py` — 151; `src/cuti/api.py` — 230; `src/cuti/cli_commands.py` — 143; `src/cuti/cli_parser.py` — 79; `src/cuti/config_specs.py` — 170; `src/cuti/config_types.py` — 78; `src/cuti/pipeline/report.py` — 196; `src/cuti/scrapers/catawiki_payload.py` — 230; `src/cuti/server.py` — 148; `src/cuti/storage/schema.py` — 155; `src/cuti/storage/schema_ddl.py` — 205; `src/cuti/storage/schema_migration.py` — 90; `frontend/src/App.vue` — 1308; `frontend/src/styles.css` — 1974; `frontend/src/types.ts` — 10; `specs/features/auction-lot-discovery.md` — 40 LOC.
- Schema additive trong `lot_images`: queue state, attempts, lỗi gần nhất, lịch retry, lease owner/expiry và queue index. Dữ liệu đã có `telegram_file_id` được migrate sang `ready`; không đổi `SCHEMA_VERSION=4`, không thêm bảng/dependency/broker.
- Sửa `tests/test_live_details.py` và `tests/test_media_vault.py` theo contract đã duyệt; không xóa test. Không xóa source trong lượt này.

## 5. Từng task được giao

- Crawler chỉ lưu tối đa một cover URL cho mỗi lot; lot không có ảnh vẫn được giữ với trạng thái `missing`, không placeholder/fallback.
- Worker riêng lấy job bằng lease và nhờ Telegram `sendPhoto` tải trực tiếp từ URL Catawiki; máy local không tải file ảnh nguồn.
- Retry chỉ cho lỗi transient, có giới hạn lần thử/backoff; lỗi permanent được lưu typed state, không nuốt lỗi.
- Web chỉ nhận same-origin `/api/media/lots/{lot_id}/cover`; bot token chỉ ở server/env và không xuất hiện trong JSON/HTML/log URL public.
- URL cover đã khóa theo `(lot_id, idx=0)`: cùng URL idempotent, URL khác conflict và không ghi đè snapshot cũ.
- Gallery nhiều ảnh được ghi deferred trong feature spec; lượt này không triển khai.
- Lean result review: `Lean already — ship` về phạm vi code; giữ retry/lease/proxy/validation. Wrapper tương thích chưa bỏ vì test nghiệm thu hiện vẫn import.

## 6. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Không còn blocker tầng 1: full verify đã xanh sau khi người dùng trực tiếp duyệt sửa contract test.
- Live Catawiki/Telegram vẫn chưa được chạy trong lượt này; cần rollout riêng để xóa `var/auctions.db*`, chạy crawler và image worker bằng credential thật.

# Vòng 25 — reset DB và rollout live có giám sát

## 1. Commit hash + ngày vận hành

- Base commit: `035e5c06ddcc21357a81beb9cc9e901697a8a5d4`.
- Ngày chạy: `2026-08-26` (Asia/Bangkok).
- Người dùng duyệt xóa không archive. DB cũ quick-check `ok`, có `lots=368`, `live_watch=3243`, `lot_images=2502`; đã xóa đúng `var/auctions.db`, `var/auctions.db-wal`, `var/auctions.db-shm`, rồi `init-db` exit `0`.

## 2. Tầng 1 — verify offline

- Sau rollout và audit cuối: `.venv\Scripts\python.exe scripts\verify.py`; raw log `var/verify/2026-08-26/verify.log`; `Ran 329 tests` dòng 398, `OK` dòng 400, `SRC_LOC_MAX=230` dòng 407, `VERIFY OK` dòng 806, `EXIT=0` dòng 808.
- Fixture live tối thiểu `tests/fixtures/catawiki_search_pages_100_101.json`; test offline đọc fixture và khóa việc dừng khi trang cuối bị lặp. Focused `test_live_watch.py`: 23 tests, exit `0`.
- `git diff --check`: exit `0`.

## 3. Tầng 2 — live rollout

- Telegram preflight `getMe=OK`, `getChat=OK`; chỉ log trạng thái, không log token/chat value.
- Crawler production `scripts/run_scheduled_crawl.py --force`: exit `0`; `[WATCH-LIVE] Seen: 2500, Tracked: 2500, Queue: 2500`; settlement lần đầu `Sold=0`, `Unsold=0`, `Lots written=0`, `Lots total=0`.
- Nguồn live báo `reported_total=10483`; pages 1–100 trả 25 lot unique/page; page 101 lặp đúng ordered IDs của page 100 và tiếp tục lặp. Dữ liệu retrievable hiện tại là 2500 unique lots. Code đã dừng ở repeated page thay vì đốt tới cap 500; vẫn kiểm conflict URL trước khi dừng.
- Image worker production đã xử lý terminal toàn bộ 2500 ảnh: `ready=2500`, không còn queued/uploading/retryable/permanent error. Thử worker thứ hai từng làm Telegram trả 429; đã dừng ngay. Các job 429 được giữ và retry thành công, không mất job/không đánh dấu ready giả.
- Audit read-only cuối: `PRAGMA quick_check=ok`, `foreign_key_check=0`, `user_version=4`; duplicate lot/live_watch/cover slot=0; orphan image=0; non-cover idx=0; invalid source URL/state/attempt=0; ready thiếu file ID hoặc còn lease/retry/error=0; token-like cell=0. Mẫu 5 ready rows đều HTTPS từ `assets.catawiki.nl`, có Telegram file ID và message ID.
- Full verify cuối xanh; image worker idle đã dừng, logical worker count=0. Heartbeat `Giám sát CUTI image queue` (`gi-m-s-t-cuti-image-queue`) hoàn tất nhiệm vụ và được xóa.

## 4. File/schema/context

- Sửa `src/cuti/pipeline/report.py`: thêm stop-on-identical-consecutive-page, vẫn giữ conflict cover URL typed error.
- Sửa `tests/test_live_watch.py`; thêm `tests/fixtures/catawiki_search_pages_100_101.json` (944 bytes, IDs/count/total tối thiểu, không URL/secret/full payload).
- `notion.md` cập nhật vận hành. Schema không đổi; không thêm dependency/config/bảng/cột/index.

## 5. Task và trạng thái

- Xóa DB cũ không archive: hoàn thành.
- Khởi tạo và crawl live từ đầu: hoàn thành; 2500 current retrievable lots được queue.
- Upload một cover/lot lên Telegram: hoàn thành 2500/2500; retry 429 đúng contract và tất cả đã về ready.
- Double-check DB cuối: hoàn thành, toàn bộ integrity/media/token invariants sạch; full verify 329/329 xanh.

## 6. Phản biện/việc còn mở

- Không còn blocker code, credential, queue hoặc DB integrity. Giới hạn thực tế là Telegram rate limit; không tăng worker sau bằng chứng 429.
- Crawler trước fix lãng phí request vì Catawiki lặp trang cuối thay vì trả empty page. Regression đã học từ live về tầng 1 bằng fixture; lần crawl sau sẽ dừng ở page 101.

# Vận hành 2026-08-27 — tạm tắt GitHub crawler

## 1. Commit hash + ngày vận hành

- Base commit: `035e5c06ddcc21357a81beb9cc9e901697a8a5d4`; ngày `2026-08-27` (Asia/Bangkok). Không commit/push hoặc đóng zip trong lượt này.

## 2. Tầng 1

- Không chạy lại verify: không sửa source, test hoặc schema; chỉ tắt workflow theo yêu cầu người dùng.

## 3. Kiểm tra vận hành GitHub

- Raw log: `var/verify/2026-08-27/github-actions-disable.log`; PowerShell version dòng 36.
- `gh workflow disable 341208948`: exit `0`, dòng 47–48. Xác nhận workflow `.github/workflows/daily_scrape.yml` là `disabled_manually`, dòng 71–73.
- Không có run queued trong truy vấn dòng 74–76; truy vấn riêng `in_progress` trả `[]`, exit `0`, dòng 79–81.
- Repository Actions secrets: `gh secret list` không trả tên secret, exit `0`, dòng 77–78. Không đọc giá trị secret.
- Trong ba đường dẫn kiểm tra, Git chỉ track `.env.example`, không track `.env` hoặc `var/auctions.db`, dòng 82–84; hai file local được ignore, dòng 85–88. Không coi đây là chứng minh chưa từng lộ secret ở mọi nơi/lịch sử.
- Lệnh chẩn đoán `gh workflow view --json` không được CLI hỗ trợ, exit `1`, dòng 60–70; kiểm tra trạng thái bằng `gh workflow list --all --json` đã thành công, dòng 71–73.
- Không chạy crawler, worker hoặc tier-2 pipeline; không sửa DB. Không có fixture UI/source mới.

## 4. File/schema/context

- Cập nhật `notion.md`, thêm raw log vận hành nêu trên. Source/test/schema không đổi; không sửa file workflow local.

## 5. Task và trạng thái

- Tạm tắt workflow cào GitHub: hoàn thành theo bằng chứng mục 3; không xóa workflow.
- Vận hành ngày mới tiếp tục DB local: mở đúng một `scripts/run_image_worker.py --limit 20 --poll-seconds 30`, rồi chạy một lượt `scripts/run_scheduled_crawl.py` từ root bằng Python trong `.venv`; không reset/init DB, không cần `--force` trong lượt thường. Đây là hướng dẫn theo code, chưa thực thi pipeline hôm nay.

## 6. Việc còn mở

- Workflow giữ trạng thái tắt đến khi người dùng yêu cầu bật lại. Chưa có cơ chế handoff/sync DB local sang GitHub hoặc workflow chạy worker ảnh. Không đưa `.env` hay key thật vào Git; triển khai cloud sau phải cấu hình secrets riêng.

# 2026-08-27 — một lệnh daily crawl và phục hồi ảnh

## 1. Commit hash + ngày thực hiện

- Base commit: `035e5c06ddcc21357a81beb9cc9e901697a8a5d4`; ngày `2026-08-27` (Asia/Bangkok). Không commit/push, không đóng zip; giữ các thay đổi có sẵn trong working tree.
- Spec/plan: `specs/features/daily-crawl-and-images.md`; phạm vi người dùng duyệt là một lệnh, một cover/lot, tự đối soát ảnh thiếu và phục hồi sau crash.

## 2. Tầng 1 — verify offline

- Baseline trước sửa: `scripts/verify.py`, 329 tests, `OK`, exit `0`; raw log `var/verify/2026-08-27/daily-baseline.log` dòng 398, 400, 808.
- Regression tái hiện lỗi split-commit trước sửa: 8 tests, 1 failure, exit `1`; `daily-queue-regressions-baseline.log` dòng 13–25 trong cùng thư mục. Không xóa/nới test để qua lỗi này.
- Full verify sau sửa: `.venv\Scripts\python.exe scripts\verify.py`; raw log canonical byte-preserving `var/verify/2026-08-27/daily-full-verify-tier1-canonical.log`: Python/package/env metadata dòng 1–50; 361 tests dòng 441; `OK` dòng 443; `SRC_LOC_MAX=230` dòng 450; `VERIFY OK` dòng 849; `EXIT=0` dòng 851. Không skip.
- 32 regression tests mới: `daily-regressions-final.log` dòng 13–16, exit `0`. Bao gồm rollback lot+cover, lease/retry, ready idempotency, đối soát lot cũ, payload thật, duplicate conflict và lỗi điều phối.
- Frontend: `frontend-typecheck-v2.log` dòng 1–4; `frontend-lint-v2.log` dòng 1–4; `frontend-build-v2.log` dòng 68–69: cả ba exit `0`. Không đổi UI.
- Lượt `daily-full-verify-final.log` chạy 364 tests khi còn gộp ba test loopback vào discovery, exit `0` dòng 836. Sau đó tách test loopback khỏi tầng 1 và chạy lại 361 tests như trên; các log trung gian được giữ nguyên, không dùng thay bằng chứng cuối.

## 3. Tầng 2 — tích hợp cách ly và nguồn thật có giới hạn

- Bốn test Windows-spawn cách ly: `daily-process-integration-t2-deterministic-final-v3.log` dòng 44–47, exit `0`. Dùng DB tạm, credential giả, HTTP giả trên loopback; kiểm tra queue drain, ready idempotency, khóa uploader và worker thoát/nhả khóa khi pipe cha đóng. Không gọi Telegram thật.
- Full-slice dùng producer/reconciliation thật với Catawiki API giả và worker con thật: log trên dòng 12–19 ghi lot mới, lot cũ thiếu cover và tổng ba ảnh ready (gồm ảnh đã có); dòng 24–27 ghi freshness skip `0.0h` ở lượt hai, không upload thêm. Đồng hồ freshness trong test được cố định và assert đúng global của producer; không phụ thuộc ngày chạy. Các log full-slice/deterministic trước v3 được giữ làm lịch sử, không dùng thay bằng chứng cuối; chỉ sửa harness, không đổi runtime.
- Nguồn Catawiki thật: hai lot ID lấy từ `live_watch` bằng SQLite `mode=ro`, hai request batch nhỏ tới endpoint hiện có, HTTP `200`; log `daily-source-smoke.log` dòng 8–12 và 19–26 (URL/status/bytes/time). Payload tối thiểu giữ đúng cấu trúc nguồn được lưu trong `tests/fixtures/daily_crawl/daily-source-payload-fixture.json`, expected riêng; test offline đọc chính fixture này.
- Cover từ endpoint chi tiết khớp chính xác snapshot đang lưu cho hai ID lấy mẫu, không normalize: `daily-source-smoke.log` dòng 27–32. Không suy rộng thành bảo đảm cho mọi lot.
- Audit production chỉ đọc: `daily-production-readonly-audit.log` dòng 1–8: cả hai snapshot đều `live_watch=2500`, `lots=0`, `lot_images=2500`, toàn bộ `ready`, `quick_check=ok`, foreign-key violations `0`.
- Checklist tầng 2: mục 1 chưa dựng máy sạch (dùng môi trường hiện có); 2–5 kiểm tra launcher cách ly và nguồn thật giới hạn như trên, không chạy production end-to-end; 6–7, 11–12 phần UI không đổi/không chạy browser; 8–10, 13–14 kiểm bằng regression transport giả và fixture nguồn thật; 15 không hiệu chỉnh kết quả nguồn; 16 không migration/schema change; 17–18 có payload fixture thật và full tầng 1 xanh. Không tuyên bố đã kiểm Telegram thật hoặc hành vi ngắt điện phần cứng.

## 4. File/schema/context

- Runtime thêm: `scripts/run_daily.py` (171 LOC), `scripts/process_lock.py` (48), `src/cuti/daily.py` (81).
- Runtime sửa: `scripts/run_image_worker.py` (164), `scripts/run_scheduled_crawl.py` (128), `src/cuti/storage/watch.py` (162), `src/cuti/storage/media.py` (202), `src/cuti/storage/__init__.py` (97), `src/cuti/scrapers/catawiki_api.py` (102), `src/cuti/scrapers/catawiki_payload.py` (230), `src/cuti/pipeline/report.py` (197), `src/cuti/telegram_media.py` (159).
- Tests thêm: `test_daily_crawl_queue_regressions.py` (289 LOC), `test_daily_storage_regressions.py` (171), `test_daily_reconciliation_regressions.py` (250), `test_daily_launcher_regressions.py` (371), helper `daily_crawl_harness.py` (99), harness riêng `daily_process_integration_t2.py` (291). Fixtures JSON nhỏ trong `tests/fixtures/daily_crawl/`.
- Docs: `README.md` (369 LOC), `specs/features/auction-lot-discovery.md` (42), spec daily mới (83), `notion.md` cập nhật evidence. Không sửa/xóa test nghiệm thu cũ trong lượt này.
- Schema/dependency/env/rate limit: không đổi. Tách helper lock để crawler và worker dùng cùng cơ chế OS lock; không thêm service/scheduler/framework.

## 5. Task và trạng thái

- Lệnh dùng hằng ngày: `.\.venv\Scripts\python.exe scripts\run_daily.py` từ root repo; giữ DB cũ, không cần reset/init-db hoặc hai cửa sổ.
- Crawler và worker riêng nhưng được một lệnh quản lý; Settings được truyền chính xác sang worker con. Từ chối uploader cạnh tranh; không coi idle là terminal khi còn retry/lease.
- Đối soát union `live_watch`/`lots` theo `lot_id`; chỉ lấy cover thật cho slot thiếu. Giữ ready và snapshot bất biến, báo missing/permanent/producer error bằng exit khác `0`.
- Lưu watch+image queue trong một transaction; queue tiếp tục lease/retry sau crash. Source errors hợp lệ vẫn cho phục hồi queue hiện có nhưng kết quả lượt chạy là nonzero.
- Lean-plan review giữ parser/queue/lock hiện có, không thêm hạ tầng. Security review đã sửa duplicate-conflict và lỗi producer bỏ qua drain. Lean-result review: `Lean already — ship`, không yêu cầu đổi runtime sau verify.

## 6. Giới hạn/việc còn mở

- At-least-once: Telegram nhận ảnh trước khi DB commit có thể dẫn tới tin nhắn trùng sau crash; không cam kết exactly-once.
- Không gửi/xóa ảnh trên Telegram thật trong lượt này; không chạy daily vào DB production. GitHub workflow vẫn tắt. Nếu test thật sau này cần cleanup, chỉ xóa đúng message ID của test theo quyền bot và giới hạn Telegram; không xóa theo khoảng ID/phỏng đoán.
- Chưa kiểm live Telegram end-to-end, Ctrl+C vật lý hoặc mất điện phần cứng; có test offline/pipe-close mô phỏng các ranh giới tương ứng. Full-slice cách ly đã kiểm tại mục 3; không dùng kết quả đó để tuyên bố đã chạy production.

# 2026-08-28 — cấu hình tham số và công thức pricing

## 1. Commit hash + ngày bàn giao

- Base commit: `035e5c06ddcc21357a81beb9cc9e901697a8a5d4`; ngày `2026-08-28` (Asia/Bangkok). Không commit/push. Working tree đã có thay đổi trước lượt này; không coi toàn bộ diff với HEAD là diff của tính năng.
- Nguồn phạm vi: `specs/formula-config.md`; giao diện `/settings`, tham số phí/tỷ giá/lợi nhuận, công thức `net_proceeds` và `profit_threshold`, helper có giới hạn. Không chuyển matching, liquidity, percentile hoặc verdict sang editor.
- Tên gói theo quy ước v20 hiện có: `.zip/cuti-tools-notion-v21-20260828.zip`. Source-only, gồm fixture và raw log; không gồm DB, `.env`, dependency, cache hoặc dữ liệu mẫu sinh lại được.
- Đây là lượt code và bằng chứng để nghiệm thu; chưa đóng vòng hai tầng vì chưa có test nghiệm thu mới và chưa chạy UI bằng CloakBrowser.

## 2. Tầng 1 — lệnh và bằng chứng

Mọi đường dẫn log trong phần này thuộc `docs/evidence/formula-config/`.

- `python scripts/verify.py`: `backend-final-contracts-02.log` dòng 2–4 ghi Python 3.12.10/lệnh; dòng 396: 361 tests; dòng 398: `OK`; dòng 405: `SRC_LOC_MAX=230`; dòng 813: currency diff clean; dòng 815: `VERIFY OK`; dòng 817: `EXIT_1=0`. Không skip.
- Chạy độc lập trên source đã freeze: `final-full-verify-02.log` dòng 398: 361 tests; dòng 400: `OK`; dòng 407: `SRC_LOC_MAX=230`; dòng 815: currency diff clean; dòng 817: `VERIFY OK`; dòng 819: exit 0.
- Bản source cách ly, Python `-S`, không nạp site-packages: `final-clean-source-S-02.log` dòng 1–6 ghi lệnh/path/thành phần copy; dòng 393: 361 tests; dòng 395: `OK`; dòng 402: exit 0. Đây là **unit suite**, không phải full `scripts/verify.py`; mẫu `data/sample` đã được đưa vào copy. Lượt `-01` thiếu mẫu nên fail; không sửa test để khắc phục.
- Full verify từ ZIP giải nén vào thư mục tạm, venv mới `--without-pip`: `package-clean-verify-v21.log` dòng 7–10 ghi extract/venv exit 0; dòng 11–13 chạy generator mẫu, exit 0. Đây là hai bước Windows tương đương `make verify` (Makefile tự sinh mẫu; `scripts/verify.py` riêng không sinh mẫu).
- Raw log canonical của full clean verify: `package-clean-verify-v21-canonical.log` dòng 1–6 ghi executable, Python 3.12.10, **không package đã cài**, không CUTI env; dòng 397: 361 tests; dòng 399: `OK`; dòng 406: LOC 230; dòng 804: currency diff clean; dòng 805: `VERIFY OK`; dòng 807: exit 0. Bản ZIP cuối giữ nguyên byte source đã kiểm, bổ sung context/evidence và workflow `.github` nguyên trạng; đóng gói YAML không chạy hoặc bật workflow.
- `npm run typecheck`: `frontend-final-typecheck-v4.log` dòng 1–15 ghi lệnh/runtime/dependencies, dòng 67: exit 0. `npm run lint`: `frontend-final-lint-v4.log` dòng 67: exit 0. Script lint hiện cũng gọi `vue-tsc --noEmit`, không phải một bộ lint độc lập.
- `npm run build`: `frontend-final-build-v4.log` dòng 1–15 ghi Node 24.19.0/npm 12.0.2/dependencies; dòng 131: build hoàn tất; dòng 132: exit 0. Không dùng build làm bằng chứng browser đã hoạt động.
- Giữ các log fail trung gian: giới hạn LOC, lỗi split/import, traversal DAG trước memo, JSON NaN và smoke fixture zero dùng nhầm shipping mặc định. Không dùng các log fail làm bằng chứng pass; không xóa/nới test để qua.

## 3. Tầng 2 — phạm vi đã chạy và chưa chạy

- Chỉ chạy probe cách ly bằng dữ liệu mẫu/DB tạm/HTTP loopback; chưa chạy UI thật hoặc nguồn Catawiki/Telegram thật trong lượt tính năng này.
- Baseline DB mở bằng SQLite `mode=ro`: `baseline-default-db-readonly.log` dòng 3; `quotes=0` dòng 20, `saved_products=0` dòng 21, `tracked_deals=0` dòng 24, exit 0 dòng 25. Đây là quan sát thời điểm baseline, không phải cam kết DB hiện tại luôn rỗng.
- Smoke backend sau sửa: `backend-final-contracts-02.log` dòng 819 ghi thiếu snapshot 400, profile không hợp lệ 422, lưu snapshot lịch sử 201, revision không khớp 422, inverse zero hợp lệ/âm bị từ chối; dòng 820–821 exit 0. Log này chỉ ghi tên smoke, không chứa toàn script nên không dùng riêng nó làm bằng chứng tái lập đầy đủ.
- HTTP sau freeze: `final-http-pricing-03.log` dòng 74–84 ghi URL/status/bytes/time và strict JSON parser không lỗi. Preview hợp lệ 200 (75), NaN bị từ chối 400 (76), custom preview 200 (79), Apply 200 (80), stale revision 409 (81), foreign Origin 403 (82), OPTIONS 204 (83); fixture `http-pricing-fixture-03.json` ghi header có `PUT`; exit 0 (86). Script thực thi nằm ngay trong log. Fixture `http-pricing-fixture.json` cũ giữ lại kết quả fail NaN, không dùng thay fixture sau sửa.
- DAG helper lặp tới h25: `final-resource-attack-03.log` dòng 22: bounded completion 0.005 giây; dòng 23: exit 0. Parity bốn input và phí bổ sung: `final-direct-math-02.log` dòng 29–36; dòng 37: exit 0. Guard kết quả inverse âm (khác input âm) và zero: `final-direct-negative-result-01.log` dòng 20–21; dòng 22: exit 0.
- Harness Windows-spawn hiện có: `final-daily-process-t2-03.log` dòng 52: 4 tests; dòng 54: `OK`; dòng 55: exit 0. DB tạm/credential giả/HTTP loopback, không phải Telegram thật. Lượt `-02` fail do thiếu `tests` trong PYTHONPATH; sửa lệnh chạy, không sửa source/test.
- HTTP fixture nằm trong thư mục evidence, không phải fixture render UI. Chưa có test tầng 1 mới đọc lại fixture này; không tuyên bố đã hoàn tất bước học lỗi tầng 2 về tầng 1.

| Mục checklist tầng 2 | Kết quả/phạm vi |
|---|---|
| 1. Máy sạch, chỉ dependency khai báo | Có ZIP giải nén + venv mới không pip/package, full verify xanh theo mục 2; chưa dựng OS sạch hoặc frontend dependency sạch. |
| 2. Khởi động một lệnh/thời gian | Chưa đo khởi động UI; giữ launcher frontend hiện có. |
| 3. Log khởi động sạch | Chưa kiểm launcher/UI thật; HTTP probe cách ly có log riêng. |
| 4. Mẫu và nguồn thật | Có dữ liệu mẫu cách ly; không chạy nguồn thật. |
| 5. Luồng chính hợp lệ | Kiểm API/core; chưa kiểm click/nhập trên UI thật. |
| 6. Parity từng số UI/core | Backend trả giá trị và chuỗi formatted; chưa có fixture render UI mới. |
| 7. Định dạng tiền/phần trăm/ngày | Chưa kiểm render UI thật. |
| 8. Đổi tham số | Probe preview/apply cách ly; không suy rộng thành kiểm UI. |
| 9. Submit hai lần | Revision conflict/snapshot được probe; chưa kiểm double-click UI. |
| 10. Input rỗng/0/âm/lớn/sai kiểu | Probe core/HTTP; chưa đi hết input UI. |
| 11. Thiếu dữ liệu | Test cũ vẫn chạy; chưa có fixture render settings thiếu dữ liệu. |
| 12. Không lộ null/Infinity/default date | Strict JSON được kiểm HTTP; chưa xác nhận mọi ô UI. |
| 13. Ngắt mạng | Chưa thử ngắt mạng trong browser. |
| 14. Nguồn field lạ/thiếu | Không thay adapter nguồn; không gọi nguồn thật. |
| 15. Kết quả thật vô lý | Không chạy dữ liệu thật, không hiệu chỉnh kết quả. |
| 16. Migration copy/rollback | Không migration/schema change; apply dùng file tạm và atomic replace. |
| 17. Fixture và test tầng 1 đọc lại | Chưa đủ: chưa có quyền thêm test nghiệm thu và chưa chạy UI. |
| 18. Chạy lại tầng 1 sau fixture/test | Suite hiện có xanh; chưa có test mới của bước 17 để chạy. |

## 4. File/schema/context

- LOC dưới đây là số dòng vật lý, không phải số dòng không rỗng; gate thực tế nằm trong output `scripts/verify.py`.
- Thêm: `src/cuti/config_pricing.py` (185), `config_pricing_math.py` (111), `config_pricing_units.py` (45), `config_pricing_store.py` (108), `api_pricing.py` (81). Tách parser/profile, phân tích inverse, kiểm đơn vị và persistence để giữ giới hạn file của repo; không thêm solver hoặc dependency.
- Sửa backend: `src/cuti/config.py` (97), `config_types.py` (81), `pricing.py` (198), `evaluation.py` (194), `price_limit.py` (44), `pipeline/quote.py` (162), `api.py` (229), `server.py` (189), `ui_views.py` (173), `app.py` (200).
- Thêm UI: `frontend/src/components/PricingSettingsPage.vue` (709). Sửa `frontend/src/App.vue` (1356), `api.ts` (61), `types.ts` (50), `components/AppIcon.vue` (104). Inventory v4 đã ghi nhầm nonempty thành physical; không dùng cột physical trong log đó.
- Context: `README.md` (394), `specs/formula-config.md` (180), `specs/IA.md` (83), `specs/SCREEN_INVENTORY.md` (100), `specs/UX_CONTRACT.md` (136), `notion.md`; evidence/acceptance cases/lean result review trong `docs/evidence/formula-config/`.
- Inventory frontend đúng: `frontend-final-inventory-v5.log` dòng 4–11 có physical/nonempty LOC và SHA256, dòng 12 exit 0. `final-manifest-02.json` có checksum baseline/current cho 17 đường dẫn được kiểm; `final-hash-equality-03.log` dòng 4–7 xác nhận 16 file ngoài `notion.md` không đổi và exit 0. Hash context khác sau khi thêm kết quả nghiệm thu; không dùng hash cũ của notion làm hash bản bàn giao.
- Schema diff: **không đổi**. Không thêm bảng/cột/index, dependency, env bắt buộc hoặc file config active thật. Profile chỉ ghi vào `config/pricing.json` khi người dùng Apply; các lần thử dùng thư mục tạm. Không xóa file source hoặc sửa test nghiệm thu trong lượt này.
- Baseline chỉ có checksums tại `baseline-snapshot.txt`, không có bản source trước sửa. Không thể dựng diff riêng toàn tính năng từ HEAD vì working tree đã dirty/untracked.

## 5. Task được giao

- Trang `/settings`: sửa sáu tham số bắt buộc, thêm/xóa tham số EUR/rate và helper, sửa hai công thức bắt buộc; preview so sánh trước/sau rồi Apply. Draft có xác nhận khi rời trang; Apply xóa evaluation đang mở nhưng giữ input và bản ghi đã lưu.
- Engine whitelist cho số hữu hạn, biến, `+ - * /`, ngoặc, `min/max`; kiểm đơn vị, cycle và giới hạn tài nguyên. Không chạy Python/eval từ công thức người dùng.
- Chỉ nhận dạng công thức giữ điều kiện affine/monotone để giá hòa vốn và giá mua tối đa còn đúng. Công thức đúng syntax nhưng không đạt điều kiện này bị từ chối.
- Profile file có revision canonical, kiểm stale write và atomic replace; thiếu file thì hiển thị env-derived/chưa lưu. File đã tồn tại nhưng sai thì báo lỗi, không quay về env.
- Quote/deal lưu bộ tham số, helper, công thức và revision trong JSON snapshot hiện có. Deal mới phải có profile tự khớp revision; không bắt khớp revision active mới hơn và không tự tính lại lịch sử.
- Lean-plan và lean-result review đã áp dụng; giữ các kiểm tra bảo toàn dữ liệu và inverse, không thêm hạ tầng dùng chung ngoài phạm vi.

## 6. Việc cần người nghiệm thu quyết định

- Cần quyền bổ sung test nghiệm thu cho engine/store/API và test đọc fixture HTTP/UI; hoặc người nghiệm thu cung cấp test để chạy theo quy trình repo. Chưa nhận quyền thì không tự viết/sửa test.
- CloakBrowser chưa có trong môi trường; cần quyền cài trong môi trường QA riêng để chạy UI thật, xuất fixture render và hoàn tất các mục UI trên. Chưa cài thêm package/browser hoặc dùng Playwright/Puppeteer thay thế.
- Chưa xác nhận vận hành production/UI end-to-end. Không coi 361 test cũ và build xanh là bằng chứng đầy đủ cho toàn bộ tính năng mới.

# 2026-08-28 — Browser QA và ba sửa lỗi UI

## 1. Commit hash + ngày bàn giao

- Base commit vẫn là `035e5c06ddcc21357a81beb9cc9e901697a8a5d4`; ngày 2026-08-28. Không commit/push. Gói cập nhật: `.zip/cuti-tools-notion-v22-20260828.zip`.
- Theo yêu cầu mới của người dùng, lượt này dùng **Codex In-app Browser**, không CloakBrowser, không cài thêm dependency. Ưu tiên DOM/text; không chụp ảnh, không kiểm pixel/thẩm mỹ mở rộng.
- Lỗi kết nối ở scope QA ban đầu được giữ trong `browser-unavailable-01.log`; kết nối ở scope Lead thành công, ghi tại `browser-dom-final-01.log` dòng 6–11. Không dùng lỗi ban đầu để kết luận Browser không khả dụng toàn phiên.

## 2. Kiểm tra offline và frontend

Mọi log/fixture dưới đây ở `docs/evidence/formula-config/`.

- `npm run typecheck`: `browser-fix-frontend-typecheck-v1.log` dòng 33, exit 0. `npm run build`: `browser-fix-frontend-build-v1.log` dòng 97–98, build hoàn tất/exit 0; runtime/dependencies/env names ở đầu mỗi log.
- Đọc lại fixture UI và đối chiếu oracle backend bằng inline Python `-S`: `browser-fixture-verify-01.log` dòng 5–33 chứa script; dòng 34–40 ghi assertions passed và exit 0. Kiểm định dạng/thứ tự output, Apply flags, thông báo thành công, tham số đã lưu, input thẩm định, no-data, không tràn ngang và không lộ NaN/Infinity.
- Không chạy lại 361 test Python vì lượt này chỉ sửa một file Vue; backend/schema/dependencies không đổi. Bằng chứng full verify 361 và venv sạch của v21 nằm ở mục trước, không khai là một lần chạy mới.
- Đây là probe inline đọc fixture, chưa phải test được đưa vào suite nghiệm thu. Không thêm, sửa, xóa hoặc nới test nguồn.

## 3. Browser thật — kết quả và giới hạn

- Môi trường cách ly: `browser-environment-setup-02.log` dòng 1–24 ghi hai lệnh chạy, port trống trước khi chạy, PID, CUTI_HOME/DB/profile tạm và health 200. Không dừng server có sẵn của người dùng. DB tạm được init schema, không có dữ liệu giao dịch thật.
- Raw Browser actions: `browser-dom-final-01.log`, gồm cả lượt trước/sau sửa. Dòng 1371 là `BROWSER_QA_EXIT=0` của các assertions cuối. Fixture DOM thực: `browser-render-fixture-01.json`; oracle backend: `browser-oracle-preview-shipping60-01.log`.
- Không có raw stdout/stderr request log của API trong lượt Browser do launcher không redirect; thiếu sót được ghi trong `browser-api-requests-unavailable-01.log`. Không suy diễn HTTP status từ DOM; bằng chứng HTTP 200/409 chi tiết là lượt cách ly trước Browser, không khai là request log của lượt này.
- Preview mặc định và phí bổ sung khớp core. Với hammer 1000, cost 100, shipping 60, packing 15: UI hiển thị `673.75 EUR`, `50.00 EUR`, `265.10 EUR`; fixture/oracle đối chiếu tại `browser-fixture-verify-01.log` dòng 34–40.
- Apply, reload giữ shipping 60/packing 15/công thức; tab thứ hai báo xung đột rồi tải được cấu hình mới: actions 9–12 trong raw Browser log. Không ghi đè profile bằng bản nháp cũ.
- Sau sửa: Apply disabled trước preview (dòng 1047), đổi input làm mất quyền Apply (1066), save xong nút trở lại disabled (1081), thông báo thành công vẫn còn ở lần đọc tiếp theo (1089).
- Sai syntax/biến không tồn tại/phép chia cho 0 bị chặn; không cho Apply. Với biểu thức chia cho 0 đã thử, validator từ chối sớm bằng `unsupported_inverse`, không phải `division_by_zero`. Lượt probe kỳ vọng mã quá cụ thể bị fail và được giữ nguyên; không đổi code để khớp kỳ vọng đó.
- Giá chào `123456`, tiền `vnd`, tình trạng `fullset` được giữ qua điều hướng/Apply **trong cùng phiên**. Không cam kết giữ input qua full page reload; probe kỳ vọng thêm điều này đã fail và được ghi là lỗi kỳ vọng ngoài contract. Trạng thái thiếu dữ liệu hiển thị rõ, không bịa kết quả.
- Native confirm khi rời draft: công cụ trả không có dialog và trang đã điều hướng; source có guard nhưng chưa xác minh được tương tác accept/cancel bằng Browser. **Inconclusive**, không ghi pass. Không sửa router/modal chỉ để phục vụ công cụ.
- Chưa chạy lưu/mở lịch sử qua UI vì DB tạm rỗng; không chạy nguồn thật hoặc mạng lỗi giữa luồng. Không kiểm đa viewport/pixel. Hai tab thử đã đóng; không đụng tab của người dùng.
- `browser-environment-final-02.log` dòng 2–12: profile chỉ có trong home tạm, DB tạm lots/quotes/deals đều 0, config pricing thật không tồn tại. `browser-environment-cleanup-01.log` dòng 1–6: chỉ dừng PID sở hữu, port 8000/4188 không còn listener, exit 0.

## 4. File/schema/context

- Chỉ sửa source `frontend/src/components/PricingSettingsPage.vue`: 714 dòng vật lý, 637 dòng không rỗng. Thêm `canApply` dùng chung cho disabled/guard, chờ Vue `nextTick()` trước thông báo thành công, sửa lời hướng dẫn helper.
- Không đổi schema, backend, API contract, dependency hoặc test source. Bổ sung raw logs/fixture Browser và cập nhật `notion.md`; các thay đổi có trước được giữ nguyên.
- Đây là ba sửa lỗi nhỏ trong UI đã có contract; không mở lại thiết kế hoặc thêm framework/state machine/modal.

## 5. Task đã làm

- Dùng Browser tích hợp để thao tác thật trên settings; ghi trạng thái DOM, đối chiếu con số backend, kiểm Apply/reload/xung đột/lỗi và input/no-data.
- Sửa ba vấn đề UI đã phát hiện và retest: hướng dẫn helper sai, nút Apply không phản ánh điều kiện chạy, thông báo thành công bị watcher xóa.
- Không chụp ảnh vì DOM và trạng thái tương tác đã đủ để kiểm các vấn đề trên; không dùng screenshot làm bằng chứng thay cho số liệu.

## 6. Phần còn mở

- Native confirm accept/cancel cần kiểm thủ công hoặc bằng cơ chế Browser hỗ trợ dialog rõ ràng; lịch sử thương vụ qua UI chưa chạy. Không khai toàn bộ checklist tầng 2 đã hoàn tất.
- Người nghiệm thu cần đưa các case/fixture mới vào suite theo quy trình repo, hoặc duyệt quyền thêm test. Probe inline đọc fixture đã chạy nhưng không thay thế regression test thường trực.

# 2026-08-28 — UI polish sau audit resolver

## 1. Commit hash + ngày bàn giao

- Base commit: `035e5c06ddcc21357a81beb9cc9e901697a8a5d4`; ngày 2026-08-28. Không commit/push.
- Người dùng đã duyệt chỉnh gọn, đơn giản, hiệu quả và nhất quán thẩm mỹ sau audit. Phạm vi được ghi tại `specs/ui-polish.md`; không đổi luồng nghiệp vụ.
- Không tạo ZIP mới ở lượt này. Chưa xác lập tên/số vòng và trần LOC trong mục 1 của AGENTS.md; không tự thay gói bàn giao cũ. Bản làm việc vẫn chứa thay đổi có trước của người dùng.

## 2. Tầng 1 — kiểm tra local/offline

Các log dưới đây nằm trong `docs/evidence/ui-polish/`.

- `npm run typecheck`: `final2-typecheck-20260828.log` dòng 1 ghi lệnh; dòng 3–18 ghi runtime/dependency/env; dòng 21 exit 0.
- `npm run build -- --outDir D:\Temp\cuti-ui-qa-20260828\dist-final3`: `final2-build-20260828.log` dòng 1 ghi lệnh; dòng 89 build 2.17 giây; dòng 90 exit 0. Build output ở thư mục QA tạm, không đưa vào source bàn giao.
- `PYTHONPATH=src; python scripts/verify.py`: `final-verify-script-20260828.log` dòng 1 ghi lệnh; dòng 399 ghi 361 tests; dòng 816 đối chiếu currency clean; dòng 818 verify OK và đường dẫn artifact cách ly; dòng 820 exit 0. Đây là chạy trên môi trường local hiện có, không phải một lần dựng máy sạch.
- Log verify dòng 4 có nhãn metadata `PYTEST_VERSION` sai (thực tế là usage của unittest), dòng 5 ghi tên manifest không chính xác. Không dùng hai dòng đó để kết luận dependency/runtime; giữ log nguyên văn, không sửa lại bằng tay. Metadata bổ sung: `final-verify-environment-supplement-20260828.log` từ dòng 3 xác định unittest và `pyproject.toml`.
- Artifact build có rule highlight autocomplete cuối: `final-build-selected-rule-check-20260828.log` dòng 3. `final-static-safeguards-corrected-20260828.log` từ dòng 3 kiểm source guard; đây là kiểm tĩnh, không phải kiểm thao tác browser.
- Các log `baseline-*`, `verify-*`, `final-*` trước `final2-*` là những lượt trước khi source chốt. Giữ cả các lỗi chạy probe ban đầu; không dùng kết quả cũ thay cho source cuối.
- Không thêm/sửa/xóa/nới test nghiệm thu. 361 test hiện có không thay thế test browser mới cho keyboard/layout đã chỉnh.

## 3. Tầng 2 — phạm vi và giới hạn

- Không chạy nghiệm thu `verify-live` đầy đủ hoặc nguồn thật. Không có fixture render/screenshot mới được chấp nhận làm bằng chứng cho lượt UI polish.
- CloakBrowser không có sẵn. Có một lần mở thử trang assessment local bằng Browser tích hợp trước khi người dùng xác nhận ngoại lệ; đã dừng, không dùng lần thử đó để tuyên bố đạt visual/keyboard gate. Không có thao tác submit/upload hoặc nguồn ngoài trong lần thử được báo cáo.
- Server QA dùng DB/base riêng: `cleanup-and-isolation-20260828.log` dòng 4–6 ghi `D:\Temp\cuti-ui-qa-20260828\qa.db`, base tạm và config check exit 0; dòng 8–11 ghi kiểm tra port/cleanup exit 0. Không dùng DB production.
- Startup/request stdout của lần mở thử không được lưu thành raw log chuyên biệt; không tái tạo log. Browser mất kết nối khi đóng tab QA, nên không xác nhận được tab đã đóng. Không đóng tab của người dùng.

| Mục checklist tầng 2 | Kết quả/phạm vi |
|---|---|
| 1. Máy sạch/dependency khai báo | Chưa dựng máy sạch; dùng môi trường local hiện có. |
| 2. Một lệnh/thời gian sẵn sàng | Chưa nghiệm thu launcher một lệnh; QA mở riêng API/UI. |
| 3. Log khởi động sạch | Chưa đủ raw startup log; không ghi pass. |
| 4. Mẫu và nguồn thật | Verify offline dùng fixture; không chạy nguồn thật. |
| 5. Luồng UI hợp lệ | Chưa kiểm hết trên browser của source cuối. |
| 6. Parity từng số UI/core | Giữ nguyên calculation contract; chưa xuất fixture UI cuối. |
| 7. Định dạng tiền/ngày/đơn vị | Chưa kiểm render đa viewport. |
| 8. Đổi tham số | Không đổi pricing/settings; chưa retest UI thật. |
| 9. Submit hai lần | Không thay contract; chưa kiểm browser cuối. |
| 10. Input lỗi | Test hiện có chạy; chưa có kiểm UI cuối cho mọi input. |
| 11. Thiếu dữ liệu | Đã sửa nhánh hiển thị; chưa có fixture browser cuối. |
| 12. Không lộ giá trị rỗng/vô hạn | Bỏ fallback độ phủ bằng 0; chưa nghiệm thu mọi ô. |
| 13. Ngắt mạng | Chưa kiểm browser. |
| 14. Field nguồn lạ/thiếu | Không gọi nguồn thật hoặc đổi adapter. |
| 15. Kết quả thật vô lý | Không chạy dữ liệu thật. |
| 16. Migration/rollback | Không đổi schema/migration. |
| 17. Fixture + test tầng 1 | Chưa có fixture UI cuối; không có quyền thêm test nghiệm thu. |
| 18. Chạy lại sau fixture/test | Verify hiện có xanh; chưa có fixture/test mới ở mục 17. |

## 4. File/schema/context

- Source sửa: `frontend/src/App.vue` — 1499 dòng; `frontend/src/styles.css` — 2031 dòng. `final-source-hashes-20260828.log` dòng 6–7 ghi SHA256, dòng 10–11 ghi LOC; dòng 13 exit 0.
- `frontend/src/components/PricingSettingsPage.vue` không đổi (714 dòng), hash đối chiếu tại `final-source-hashes-20260828.log` dòng 8, 12. Không đổi backend, API/schema, package manifest/lockfile hoặc test source.
- Context thêm: `specs/ui-polish.md` (phạm vi, kế hoạch, lean reviews, trạng thái kiểm tra). Context sửa: mục hiện tại của `notion.md`. Raw logs được thêm trong `docs/evidence/ui-polish/`; không xóa log fail/cũ để che kết quả.
- LOC/hash của source, context và từng raw log được liệt kê trong `docs/evidence/ui-polish/final-artifact-inventory-20260828.log` (không tự hash file inventory).
- Schema diff: **không đổi**. Không tách source file hoặc thêm component framework.
- Bản source trước sửa được giữ ở `D:\Temp\cuti-ui-preflight-20260828-122158-dc98126c\`; dùng đối chiếu riêng lượt này vì frontend vốn untracked. Đây là snapshot QA ngoài repo, không phải gói bàn giao.

## 5. Task đã làm

- Đồng bộ palette CUTI sáng/tối; bỏ gradient/blur/status glow, giảm viền/shadow của form/record; giữ decision region là điểm nhấn, giữ dữ liệu và ảnh nguồn.
- Thêm nhãn cho record mobile, input cơ sở 16px, target retry 44px và motion route 100ms ra/140ms vào.
- Bổ sung autocomplete ARIA/keyboard/highlight/Escape, tab controls/tabpanel, tên dialog/focus containment/inert nền; giữ toast feedback.
- Tách loading/error/empty/no-match, thêm retry/xóa bộ lọc hiện tại; không reset filter tab khác, không dùng 0 thay độ phủ chưa có.
- Giữ Vue/CSS hiện có. Không cài component từ resolver vì audit không tìm được ứng viên tương thích; không đổi framework hay mở rộng registry.
- Lean-plan và lean-result review giữ các kiểm soát accessibility/data; không thêm dependency hoặc lớp trừu tượng mới. Chưa kết luận UI đạt thẩm mỹ/đa viewport chỉ từ build xanh.

## 6. Việc còn cần xác nhận

- Đã hỏi quyền dùng Browser tích hợp thay CloakBrowser cho lượt này; chưa có câu trả lời tại thời điểm ghi mục này. Cần kiểm thực tế 1440/1024/768/390/320px, light/dark, reduced motion và keyboard trước khi chốt visual gate.
- Người nghiệm thu cần cung cấp/duyệt test regression mới cho autocomplete/tab/dialog/state và fixture render. Không tự thêm test nghiệm thu.
- Chưa đủ điều kiện tuyên bố máy sạch/full verify-live hoặc giao ZIP mới theo metadata còn trống. Không dùng bằng chứng local thay cho các phần chưa kiểm.
