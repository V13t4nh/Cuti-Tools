# Bàn giao vòng 13 — giá sàn Buyer, cap deal đỏ và frozen-file evidence

## 1. Commit hash + ngày đóng gói

- Source commit: `b41da24ec4877bfeeed107f34f7ca659d8029c3c`.
- Ngày đóng gói: 2026-08-20 (Asia/Bangkok).
- `NOTION_SANDBOX/PROVENANCE.json` dùng cùng source commit.

## 2. Tầng 1 — verify offline

- Raw log: `var/verify/2026-08-20/verify.log`. Các mốc grep-able có mặt: `COMMAND=`, `PYTHON_VERSION=`, `PACKAGES_BEGIN`, `PACKAGES_END`, `CUTI_ENV_NAMES=`, `LIVE_FIXTURES=`, `Ran 301 tests`, `SRC_LOC_MAX=`, `ALERTS_SENT=`, ba dòng `FROZEN_SHA256`, `EXIT=0`.
- Tầng 1 chạy offline: 301 test, 0 fail, 0 skip, exit 0. `LIVE_FIXTURES=0`, `ALERTS_SENT=1`.

## 3. Tầng 2 — verify-live

- Không chạy theo prompt. Không tạo fixture trong `tests/fixtures/live/`, không gọi mạng.
- Trạng thái fixture/live cũ không đổi: `var/live/2026-08-20/fetch-lots.log` vẫn chứa HTTP 403 trước đó.

## 4. File thêm / sửa / xoá, kèm LOC sau khi sửa

Sửa:

- `scripts/verify.py` — 200 LOC.
- `src/cuti/app.py` — 123 LOC.
- `src/cuti/cli_commands.py` — 128 LOC.
- `src/cuti/evaluation.py` — 194 LOC.
- `src/cuti/pipeline/quote.py` — 160 LOC.
- `src/cuti/price_limit.py` — 39 LOC.
- `tests/test_app.py` — 189 LOC.
- `tests/test_evaluation.py` — 227 LOC.
- `tests/test_scale2_watch.py` — 119 LOC.
- `tests/test_verify_scripts.py` — 158 LOC.
- `var/verify/2026-08-20/verify.log` — 580 LOC, raw log tự sinh.
- `NOTION_SANDBOX/PROVENANCE.json` — 11 LOC.
- `notion.md` — cập nhật lúc đóng gói.

Thêm/xoá: không có.

Contract đã duyệt: JSON `cuti evaluate` đổi từ 15 sang 16 khóa, thêm duy nhất `max_buy_cost_vnd`.

Diff schema: không đổi bảng, cột, index hoặc kiểu dữ liệu; `src/cuti/storage/schema_ddl.py` không bị sửa.

## 5. Từng task được giao

- T1: `max_buy_cost_vnd(hammers, days_to_close, settings)` nhận full pool và hỏi green bằng `pricing.quote(...).verdict`; không còn gọi `decide` ngoài `pricing.py`. Test lock cap 6×5000 EUR là `98814130`, cap green, cap + 1 không green, pool mỏng `None`.
- T2: cap được tính cho mọi pool đủ mẫu, không phụ thuộc verdict của chi phí hiện tại. `DealEvaluation` và CLI JSON phơi `max_buy_cost_vnd`; cost đỏ vẫn có cap. Alert chỉ tạo khi verdict green và ask không vượt cap; test deal đỏ xác nhận outbox rỗng.
- T3: app chỉ render metric `Giá nhập tối đa (VNĐ)` bằng đúng field evaluator trả về, ẩn nhãn khi null. Recorder test kiểm parity, không có số học/làm tròn/đổi tiền trong UI.
- T4: `scripts/verify.py` có một hằng số danh sách ba file cấm sửa và log SHA-256 byte-level đúng thứ tự trước `EXIT=`. Test kiểm hash bytes tạm, lỗi thiếu file có kiểu `FrozenFileError`, và ba marker deterministic.

## 6. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Prompt nói SHA-256 của ba file phải khớp các MD5 đã chốt nhưng không cung cấp ba MD5 để đối chiếu chéo. Raw log đã ghi SHA-256 thực của `pricing.py`, `storage/schema_ddl.py`, `rules.json`; cần cung cấp MD5 nếu vẫn muốn thực hiện đối chiếu này.
- Không thêm dependency/env/schema, không sửa `pricing.py`, DDL hoặc `config/rules.json`. Evaluate EUR/VNĐ đã kiểm trực tiếp byte-identical; net `1382.0278125 / 1522.28375 / 1827.6215625`, green, sample 8.
