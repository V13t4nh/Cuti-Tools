# CUTI-Tools

Công cụ hỗ trợ quyết định arbitrage đồng hồ: thu thập auction đã kết thúc, khớp
đúng reference và tình trạng, tính net p25/median/p75, hiển thị đèn
Xanh/Vàng/Đỏ, theo dõi deal và xếp hạng thanh khoản.

Roadmap và ranh giới kiến trúc nằm tại [`mermaid.md`](mermaid.md). Toàn bộ
roadmap đã chạy end-to-end bằng dữ liệu mẫu. Hai adapter lấy dữ liệu thật
(Catawiki và Facebook/marketplace) được để riêng cho giai đoạn tích hợp nguồn.

## Chạy nhanh trên Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe scripts\generate_sample_data.py
.\.venv\Scripts\python.exe scripts\verify.py
```

`verify.py` chạy toàn bộ test và luồng thật
`init-db → ingest → quote → watch → liquidity → report` trên một thư mục riêng
trong `var/verify/`. Script không xóa database hay artifact có sẵn.

`CUTI_MATCH_THRESHOLD` dùng thang phần trăm 0–100 (mặc định `85`).

## Chạy công cụ với dữ liệu mẫu

```powershell
.\.venv\Scripts\cuti.exe --today 2026-08-01 init-db
.\.venv\Scripts\cuti.exe --today 2026-08-01 ingest
.\.venv\Scripts\cuti.exe --today 2026-08-01 quote `
  --title "Omega Speedmaster Professional 311.30.42 full set" `
  --cost-vnd 30000000 --condition fullset --form round
.\.venv\Scripts\cuti.exe --today 2026-08-01 watch
.\.venv\Scripts\cuti.exe --today 2026-08-01 liquidity
.\.venv\Scripts\cuti.exe --today 2026-08-01 report
.\.venv\Scripts\cuti.exe status
```

Mở giao diện buyer một trang:

```powershell
.\.venv\Scripts\python.exe -m streamlit run src\cuti\app.py
```

Giao diện có form chấm deal, comparables, histogram giá kèm vạch giá vốn,
median theo quý, gia tốc tim và bảng thanh khoản theo `brand + form`.

## Bắt giá búa thật từ Catawiki (2 pha)

Catawiki không cho tìm kiếm lot đã đóng: search chỉ trả lot đang mở, và trang
lot cũ sẽ hết hạn sau vài tháng. Vì vậy giá búa chỉ lấy được theo hai pha:

```powershell
.\.venv\Scripts\cuti.exe watch-live    # pha 1: xếp hàng lot đang mở + ngày đóng
.\.venv\Scripts\cuti.exe settle        # pha 2: lot đã đóng thì đọc giá búa
.\.venv\Scripts\cuti.exe check-urls    # hàng tuần: URL nào còn xem lại được
.\.venv\Scripts\cuti.exe ingest-lot --url https://www.catawiki.com/en/l/105916285-rolex
```

- `watch-live` đọc `search` rồi `lots/live` để lấy `bidding_end_time`, ghi vào
 bảng `live_watch`. Pha này chưa có giá — đúng bản chất đấu giá đang chạy.
- `settle` chỉ xử lý lot đã quá ngày đóng, đọc `bidding_block` để lấy `is_sold`,
 `highest_bid_amount`, `bids_count`, đồng thời snapshot `favorite_count` thành
 `hearts`, rồi xoá lot khỏi `live_watch`.
- Lot bị Catawiki xoá trước khi chốt được đếm là `vanished`. Title không nói rõ
 tình trạng được đếm là `unclassified` và bị bỏ, không đoán bừa condition.
- `check-urls` đặt `source_available = '__NO__'` khi trang lot hết hạn. Redirect
 về trang category vẫn trả 200 nên phải kiểm tra `/l/{lot_id}` trong URL cuối.
 Giá đã lưu vẫn dùng làm comparable, chỉ là không xác minh lại được ở nguồn.
- Nhịp gợi ý: `watch-live` + `settle` mỗi ngày, `check-urls` mỗi Chủ nhật. Giữ
 `CUTI_CATAWIKI_PAUSE_SECONDS >= 1` và `CUTI_CATAWIKI_BATCH_SIZE = 50`.

## Luồng quyết định

```text
nguồn → parse/preflight toàn batch → normalize → SQLite
      → exact brand/model identity/condition → SequenceMatcher >= ngưỡng
      → sold prices + tổng attempts
      → pricing p25/median/p75 → snapshot audit
      → SQLite outbox → file hoặc Telegram
```

Với model không có reference, `identity_tokens` trong `config/rules.json` giữ
các thuộc tính ảnh hưởng mạnh tới giá như `automatic`, `quartz`, `manual`,
`solar` và `kinetic`; khác identity thì không được dùng chéo comparables. Số
4 chữ số trong khoảng năm chỉ được coi là reference khi có cue `ref` hoặc
`reference`; nếu không, nó bị loại khỏi model key để tránh trộn năm sản xuất.
Matching đọc toàn bộ candidate trong cửa sổ cấu hình, không cắt ngầm theo số
lượng.

Công thức pricing chỉ tồn tại tại `src/cuti/pricing.py`:

```text
fee       = hammer * commission_rate
net       = hammer - fee * (1 + VAT_on_fee) - shipping - cost
threshold = max(cost * min_margin_rate, min_profit_eur)

green             net(p25) > threshold
yellow            net(median) > threshold >= net(p25)
red               net(median) <= threshold
insufficient_data sold comparables < min_comparables
```

Unsold lot không đi vào percentile nhưng vẫn đi vào `attempt_count` và
sell-through. Mỗi quote lưu bản sao comparables cùng toàn bộ assumption và hash
của rules, nên audit không thay đổi khi dữ liệu lot về sau được cập nhật.

## Contract dữ liệu mẫu

Auction HTML yêu cầu dữ liệu rõ ràng, không suy đoán:

```html
<div class="lot-card"
     data-lot-id="cw-00001"
     data-title="Omega Seamaster 210.30.42 full set"
     data-condition="fullset" data-form="round"
     data-hearts="42" data-sold="true" data-hammer-eur="3200"
     data-opened-at="2026-05-05" data-ended-at="2026-05-12"
     data-url="lots/cw-00001.html"></div>
```

Deal feed là JSON array với đủ các field:

```json
{
  "source": "fb-group",
  "title": "Omega Seamaster 210.30.42 with box",
  "ask_vnd": 70000000,
  "url": "https://example.invalid/deal/1",
  "seen_at": "2026-08-01",
  "condition": "box",
  "form": "round"
}
```

Batch malformed hoặc unknown brand dừng trước lần ghi DB đầu tiên. Deal cũ hoặc
future-dated không được lưu. Dedupe dùng `UNIQUE(sha256)` trong SQLite.

## Cấu hình và Telegram

Copy `.env.example` thành `.env`, sau đó chỉnh các biến cần thiết. Giá trị từ
process environment ưu tiên hơn `.env`; biến `CUTI_*` không biết sẽ bị từ chối
để tránh typo im lặng.

```dotenv
CUTI_NOTIFIER=telegram
CUTI_TELEGRAM_BOT_TOKEN=...
CUTI_TELEGRAM_CHAT_ID=...
```

### Ngưỡng dữ liệu so sánh

`CUTI_MIN_COMPARABLES` chi phối verdict theo **số lot đã bán**. Trong khi đó,
`sell_through_rate` và `heart_to_hammer_rate` chỉ được tính khi **tổng số lot
trong pool** (đã bán và chưa bán) đạt ngưỡng này. Vì vậy pool có 6 lot nhưng
chỉ 2 lot đã bán sẽ trả `insufficient_data`, đồng thời vẫn báo
`sell_through_rate = 0.33`; không có Net Profit được suy đoán.

Alert Xanh được ghi vào SQLite outbox cùng transaction với quote. Nếu Telegram
lỗi, alert trở lại trạng thái pending và retry ở lần `watch` sau; quá số lần cấu
hình sẽ vào `dead`, không bị báo nhầm là đã gửi. Outbox vẫn được drain nếu fetch
hoặc parse feed mới thất bại. `cuti watch` in lỗi delivery và trả exit code khác
0 để cron/Task Scheduler không báo thành công giả.

### Kiểm tra Details của một lot (smoke test thủ công)

Đường này chỉ tải và parse một trang, không mở kết nối SQLite và không ghi DB:

```text
cuti fetch-lot-details --url https://www.catawiki.com/en/l/123456-example
cuti fetch-lot-details --lot-id 123456
```

Kết quả luôn là JSON gồm các trường Details đã parse được. Để lấy Details trong
`settle` hoặc `ingest-lot`, bật `CUTI_DETAILS_ENABLED=true`; mặc định tắt để các
lệnh verify và chạy offline không gọi mạng.

Form Streamlit không mặc định tình trạng hoặc form vỏ: buyer phải xác nhận rõ
cả hai trước khi hệ thống tạo quote. Audit cũ không có snapshot được đánh dấu
`legacy_snapshot=unavailable`, thay vì được trình bày như quote replayable.

## Cấu trúc

```text
src/cuti/
  app.py          Streamlit một trang
  charts.py       ba biểu đồ Plotly
  pipeline.py     ingest / watch-live / settle / quote / watch tuyến tính
  scrapers/       catawiki_api.py (JSON 2 pha), catawiki.py (HTML), deals.py
  storage.py      SQLite schema v3, FTS5, live_watch, migration, audit, outbox
  normalize.py    brand/reference/identity/condition và RapidFuzz
  comparables.py  exact gates + fuzzy threshold + time window
  pricing.py      công thức duy nhất
  liquidity.py    brand + form, QoQ và cảnh báo ngừng nhập
  notifier.py     file JSONL hoặc Telegram
  cli.py          adapter dòng lệnh
config/rules.json vocabulary, identity tokens và reference pattern
data/sample/      384 auction lots + deal feed deterministic
tests/            unit, integration, migration và end-to-end
```

Repo có index CodeGraph tại `.codegraph/` để tra symbol, call path và blast
radius khi tiếp tục phát triển.

## Ranh giới YAGNI

- Không Postgres, ORM, Redis, service queue, API riêng, Docker stack, ML hay
 vector database.
- SQLite outbox là một bảng nhỏ để bảo đảm không mất alert, không phải hạ tầng
 queue riêng.
- Chưa có daemon/scheduler trong app; production dùng cron hoặc Task Scheduler.
- Adapter Catawiki thật đã có (`scrapers/catawiki_api.py`, JSON buyer endpoint,
 stdlib-only). Chưa có Playwright, proxy, hay quét theo dải lot id.
- Chưa triển khai crawler Facebook/marketplace thật. Khi làm, chỉ thay adapter
 đầu vào; normalization, pricing, audit, UI, liquidity và notifier giữ nguyên.
- Không lưu ảnh, không lưu sổ từng lần đấu. Chỉ snapshot `hearts` và
 `bids_count` tại thời điểm đóng — đủ để đo sức nóng, không phình database.
