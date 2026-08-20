# Bàn giao vòng 11 — Scale 1 Buyer và chặn xác nhận fixture rỗng

## 1. Commit hash + ngày đóng gói

- Source commit: `05a905fe78566f44de594d613cf71823553cd217`.
- Ngày đóng gói: 2026-08-20 (Asia/Bangkok).
- `NOTION_SANDBOX/PROVENANCE.json` dùng cùng source commit.

## 2. Tầng 1 — verify offline

- Raw log: `var/verify/2026-08-20/verify.log`; dòng 1 là lệnh, dòng 51 là `LIVE_FIXTURES=0`, dòng 357 là `Ran 291 tests`, dòng 359 là `OK`, dòng 564 là `SRC_LOC_MAX=230`, dòng 566 là `EXIT=0`.
- Không có skip hoặc request mạng trong tầng 1.

## 3. Tầng 2 — verify-live

- Không chạy trong vòng này theo prompt. Chưa có HTML người tải; trạng thái 403 trước đó còn nguyên tại `var/live/2026-08-20/fetch-lots.log`, dòng 51 (HTTP 403/392 byte), dòng 98 (`EXIT=1`).
- Fixture lưu mới: không có; `LIVE_FIXTURES=0` được ghi tại tầng 1, dòng 51.

## 4. File thêm / sửa / xoá, kèm LOC sau khi sửa

Sửa:

- `AGENTS.md` — 145 LOC (policy người dùng cập nhật).
- `scripts/verify.py` — 155 LOC.
- `src/cuti/evaluation_chart.py` — 173 LOC.
- `tests/test_app.py` — 130 LOC.
- `tests/test_charts_scale1.py` — 57 LOC.
- `tests/test_verify_scripts.py` — 76 LOC.
- `var/verify/2026-08-20/verify.log` — 566 LOC, raw log tự sinh.
- `NOTION_SANDBOX/PROVENANCE.json` — 11 LOC.
- `notion.md` — cập nhật lúc đóng gói.

Thêm/xoá: không có.

Diff schema: không đổi bảng, cột, index hoặc kiểu dữ liệu; `src/cuti/storage/schema_ddl.py` không bị sửa.

## 5. Từng task được giao

- T1: `scripts/verify.py` đếm đúng chỉ file `.html` thật trong `tests/fixtures/live/`, ghi/in `LIVE_FIXTURES=<n>` trước test. Test kiểm thư mục không có/không tồn tại ra 0, bỏ qua file không phải HTML và thư mục có đuôi `.html`, đồng thời kiểm raw log + stdout có `LIVE_FIXTURES=0`. Không tạo fixture giả, không skip.
- T2: accessor chart trả cả `cycle_position` và `heart_acceleration_rate`; pool dưới `CUTI_MIN_COMPARABLES` trả `(None, None)` trước khi tính. UI đọc trực tiếp hai field này, chỉ render khi khác `None`. Không thêm field vào `DealEvaluation`, dependency, env hoặc số học UI.
- T3: test parity offline dùng cùng `BuyerEvaluation.chart` để assert app hiển thị nguyên giá trị `cycle_position`/`heart_acceleration_rate`, và ẩn cả hai khi `None`. Test helpers sẵn có giữ ca chu kỳ tăng/gia tốc dương và chu kỳ giảm/gia tốc âm; test accessor bổ sung ca pool mỏng cả hai `None`.
- T4: raw tầng 1 chứa `COMMAND=`, môi trường, `LIVE_FIXTURES=0`, `SRC_LOC_MAX=230`, `EXIT=0`; line-pointer nằm ở mục 2. `AGENTS.md` được đưa vào source commit theo chỉ dẫn.

## 6. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Không có thay đổi spec cần xin duyệt. Tầng 2 và bốn HTML browser vẫn là nợ đã được prompt loại khỏi Vòng 11; không gọi lại mạng.
- Không thêm dependency/env, không sửa `pricing.py`, DDL hoặc `config/rules.json`. `pricing.quote` vẫn được test gọi một lần cho mỗi pool; JSON CLI và số tiền không đổi qua suite offline.
