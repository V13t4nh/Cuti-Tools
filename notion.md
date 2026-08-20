# Bàn giao vòng 14 — Scale 3: thanh khoản có trục thời gian

## 1. Commit hash + ngày đóng gói

- Source commit: `061e0bd50a5a666173d58cb480d901668bd044a8`.
- Ngày đóng gói: 2026-08-20 (Asia/Bangkok).
- `NOTION_SANDBOX/PROVENANCE.json` dùng cùng source commit.

## 2. Tầng 1 — verify offline

- Lệnh đã chạy: `make verify` với Python project đã khai báo.
- Raw log: `var/verify/2026-08-20/verify.log` — các mốc `COMMAND=`, `PYTHON_VERSION=`, `PACKAGES_BEGIN`/`PACKAGES_END`, `CUTI_ENV_NAMES=`, `LIVE_FIXTURES=`, `Ran 309 tests`, `SRC_LOC_MAX=230`, ba `FROZEN_SHA256`, `ALERTS_SENT=`, `EXIT=0`.
- Kết quả: pass; 309 test, 0 fail, 0 skip, exit 0. Ba `FROZEN_SHA256` xuất hiện trước `EXIT=0`.

## 3. Tầng 2 — verify-live

- Đã thử chạy; thất bại HTTP 403 khi lấy lot Catawiki (`var/live/2026-08-20/fetch-lots.log`), chưa có fixture HTML thật.
- Chưa đủ bằng chứng để deploy nguồn thật; cần xử lý nguồn truy cập và chạy lại verify-live.

## 4. File thêm / sửa / xoá, kèm LOC sau khi sửa

Sửa:

- `src/cuti/app.py` — 140 LOC.
- `src/cuti/cli_commands.py` — 128 LOC.
- `src/cuti/evaluation_chart.py` — 190 LOC.
- `src/cuti/liquidity.py` — 195 LOC.
- `var/verify/2026-08-20/verify.log` — raw log tự sinh.
- `NOTION_SANDBOX/PROVENANCE.json` — cập nhật lúc đóng gói.
- `notion.md` — cập nhật lúc đóng gói.

Lượt này ghi chú deploy, không đổi code/schema.

Thêm:

- `src/cuti/liquidity_timeline.py` — 102 LOC.
- `tests/test_app_liquidity.py` — 87 LOC.
- `tests/test_liquidity_scale3.py` — 105 LOC.

Xoá: không có.

Diff schema: không đổi bảng, cột, index hoặc kiểu dữ liệu; `src/cuti/storage/schema_ddl.py` không bị sửa. `pyproject.toml` giữ `dependencies = []`.

## 5. Từng task được giao

- T1: thêm chuỗi quý hoàn tất theo `CUTI_COMPARABLE_WINDOW_DAYS`; mỗi cửa sổ phơi sell-through, heart-to-hammer, median days và sample size. Cửa sổ thiếu mẫu là `None`; cutoff ngày cấu hình được áp dụng cả cho quý đầu không trọn.
- T2: thêm `declining` / `stable` / `improving` theo `CUTI_LIQUIDITY_DECLINE_RATE` cho `cuti liquidity`; thiếu hai cửa sổ liền nhau trả `None`. Test khóa omega 0.935, oris 0.875, rolex 0.858, citizen 0.847, seiko 0.834.
- T3: Buyer nhận chuỗi qua chart accessor, chỉ chuyển giá trị thô vào `st.metric`/`st.bar_chart`; ẩn phần khi accessor `None` và ẩn metric riêng thiếu dữ liệu. Không thêm khóa JSON `cuti evaluate`.
- T4: `evaluation.py` giữ 194 LOC; `liquidity.py` 195 LOC, nên không cần tách thêm. Tất cả `src/cuti/*.py` không quá 230 LOC, theo mốc `SRC_LOC_MAX=230`.

## 6. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Chưa nên deploy production unattended. Trước khi deploy: sửa `CUTI_MATCH_THRESHOLD=85`, fail-fast khi còn nguồn mẫu, rehearsal backup/rollback migration, và recovery/lock cho outbox.
- Cần pin runtime/dependency, chốt scheduler + persistent volume; nếu public thì thêm auth/TLS.
