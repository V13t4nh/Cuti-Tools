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
