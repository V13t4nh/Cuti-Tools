# Bàn giao vòng 12 — Scale 2 offline: giá sàn và alert outbox

## 1. Commit hash + ngày đóng gói

- Source commit: `eca10f12aa086434b5fcbd0b7e32dfa34ce8d478`.
- Ngày đóng gói: 2026-08-20 (Asia/Bangkok).
- `NOTION_SANDBOX/PROVENANCE.json` dùng cùng source commit.

## 2. Tầng 1 — verify offline

- Raw log: `var/verify/2026-08-20/verify.log`. Các mốc theo tên: `COMMAND=`, `CUTI_ENV_NAMES=(none)`, `LIVE_FIXTURES=0`, `Ran 296 tests`, `SRC_LOC_MAX=230`, `ALERTS_SENT=1`, `EXIT=0`.
- Tầng 1 chạy offline; 296 test, 0 fail, 0 skip. `ALERTS_SENT=1` được đọc từ `alert_outbox` của chính database workflow mẫu.

## 3. Tầng 2 — verify-live

- Không chạy trong vòng này theo prompt. Không có fixture HTML mới. Trạng thái 403 cũ còn nguyên tại `var/live/2026-08-20/fetch-lots.log` (mốc `REQUEST ... status=403`, `EXIT=1`).

## 4. File thêm / sửa / xoá, kèm LOC sau khi sửa

Sửa:

- `scripts/verify.py` — 173 LOC.
- `src/cuti/pipeline/quote.py` — 157 LOC.
- `tests/test_verify_scripts.py` — 111 LOC.
- `var/verify/2026-08-20/verify.log` — 572 LOC, raw log tự sinh.
- `NOTION_SANDBOX/PROVENANCE.json` — 11 LOC.
- `notion.md` — cập nhật lúc đóng gói.

Thêm:

- `src/cuti/price_limit.py` — 41 LOC; tách để luật giá sàn chỉ tồn tại một nơi.
- `tests/test_scale2_watch.py` — 110 LOC.

Xoá: không có.

Env mới: không có; dùng `CUTI_MIN_MARGIN_RATE` và `CUTI_MIN_PROFIT_EUR` sẵn có.

Diff schema: không đổi bảng, cột, index hoặc kiểu dữ liệu; `src/cuti/storage/schema_ddl.py` không bị sửa.

## 5. Từng task được giao

- T1: thêm `max_buy_cost_vnd(price, settings)`. Hàm nhận `PriceQuote` của pool đã đánh giá, trả giá VNĐ nguyên lớn nhất còn green tại p25; pool mỏng/không có p25 trả `None`. Hàm gọi lại `vnd_to_eur`, `profit_threshold`, `net_proceeds`, `decide` từ pricing; không có công thức fee thứ hai. Test dùng `quote` thật để chứng minh cap green, cap + 1 không green.
- T2: `quote_watch` vẫn tìm pool và gọi `pricing.quote` đúng một lần, sau đó chỉ tạo payload outbox khi deal green và `ask_vnd <= max_buy_cost_vnd`. Test chạy `watch_deals` hai lần cùng SQLite/local feed, còn đúng một outbox row; deal vượt cap không tạo alert mới.
- T3: test notifier luôn ném lỗi chạy qua `watch_deals` thật: attempts 1/pending, attempts 2/dead (theo `CUTI_ALERT_MAX_ATTEMPTS=2`), không row nào `sent`, và lần kế tiếp không retry vô hạn.
- T4: raw log đổi empty marker thành `CUTI_ENV_NAMES=(none)`; thêm `ALERTS_SENT=<n>` trước `EXIT=`. Test kiểm count chỉ tính row `sent`, marker console/raw khi không fixture, và marker empty env.

## 6. Phản biện spec, câu hỏi, thứ cần xin duyệt

- `pricing.decide` hiện dùng biên strict: p25 net phải **lớn hơn** threshold mới green. Vì `pricing.py` cấm sửa, “giá đúng ngưỡng” được triển khai là giá VNĐ nguyên lớn nhất mà `quote` thật trả green; thêm 1 VNĐ không green. Đây là ca boundary kiểm trực tiếp qua pricing, không đổi công thức.
- Không thêm dependency/env/schema, không sửa `pricing.py`, DDL hoặc `config/rules.json`. Tầng 2 và HTML người tải vẫn ngoài phạm vi Vòng 12; không gọi mạng.
