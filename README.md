# CUTI-Tools

## Product specifications

- [Information Architecture](./specs/IA.md)
- [Product Search](./specs/features/product-search.md)
- [Saved Items](./specs/features/saved-items.md)
- [Auction Lot Discovery](./specs/features/auction-lot-discovery.md)
- [Liquidity Market](./specs/features/liquidity-market.md)
- [Core Journey: Thẩm định cơ hội mua](./specs/journeys/assessment.md)
- [Global UX Rules](./specs/GLOBAL_UX_RULES.md)
- [Responsive UX Contract](./specs/RESPONSIVE_CONTRACT.md)
- [Motion and Page Transition Contract](./specs/MOTION_CONTRACT.md)
- [UX Contract](./specs/UX_CONTRACT.md)
- [Screen Inventory and UI Readiness](./specs/SCREEN_INVENTORY.md)

Công cụ hỗ trợ quyết định arbitrage đồng hồ: thu thập auction đã kết thúc, khớp
đúng reference và tình trạng, tính net p25/median/p75, hiển thị đèn
Xanh/Vàng/Đỏ, theo dõi deal và xếp hạng thanh khoản.

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
Lượt verify hiện chạy 323 test; marker `LOGIC_COVERAGE_VERDICTS` được đo từ các
verdict thực nhận khi evaluate fixture logic coverage và sắp xếp xác định.

`CUTI_MATCH_THRESHOLD` dùng thang phần trăm 0–100 (mặc định `85`).

## Frontend sản phẩm

Frontend Vue 3 + TypeScript + Vite nằm trong `frontend/`, dùng trực tiếp REST API
với các route `/assessment`, `/tracking`, `/market`, `/settings`. Cài dependency đã khai
báo rồi chạy toàn hệ thống bằng một lệnh:

```powershell
cd frontend
npm install
npm run dev
```

`npm run dev` quản lý cả API Python và Vite; `npm run preview` build production
rồi chạy API cùng preview server. Database, catalog canonical và nguồn dữ liệu
được điều khiển bởi cấu hình CUTI hiện có. Frontend không có fixture/fallback
production và không tính lại luật thẩm định.

Kiểm tra frontend:

```powershell
npm run typecheck
npm run lint
npm run build
```

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

Streamlit chỉ còn là công cụ nội bộ/legacy:

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

Công thức pricing mặc định được giữ trong cấu hình engine; `src/cuti/pricing.py`
dùng engine chung cho các luồng tính. Với cấu hình ban đầu, quy tắc là:

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

### Cấu hình tính toán

Mở `/settings` để sửa mức phí, tỷ giá, biên lợi nhuận, lợi nhuận tối thiểu,
hoặc thêm tham số và công thức phụ. Hai kết quả bắt buộc là `net_proceeds` và
`profit_threshold`. Biểu thức hỗ trợ biến đã khai báo, `+ - * /`, dấu ngoặc,
`min()` và `max()`; không chạy mã Python tùy ý.

Khoản tiền trong biểu thức dùng EUR; tỷ lệ nhập dưới dạng số thập phân
(ví dụ `0.1` tương ứng 10%). Tỷ giá có đơn vị VND/EUR. Chọn **Chạy thử** với
cùng giá bán và giá vốn để xem kết quả trước/sau do backend tính và định dạng,
sau đó mới **Áp dụng**. Sửa bản nháp phải chạy thử lại.

Cấu hình chưa lưu lấy rõ ràng từ env hiện tại. Áp dụng thành công mới tạo
`config/pricing.json` trong thư mục home của CUTI; file này trở thành nguồn
pricing có hiệu lực. File đã lưu nhưng không hợp lệ sẽ báo lỗi, không quay
âm thầm về env. Preview không ghi file hay DB. Không thay đổi schema DB.

Engine chỉ nhận công thức bảo đảm tính được giá hòa vốn và giá mua tối đa:
lợi nhuận phải tuyến tính theo giá bán/giá vốn, tăng theo giá bán và giảm theo
giá vốn; ngưỡng lợi nhuận không giảm theo giá vốn. Công thức ngoài phạm vi sẽ
bị từ chối. Kết quả lưu giữ snapshot công thức và tham số đã dùng; áp dụng
cấu hình mới không sửa lịch sử. Xem [đặc tả](specs/formula-config.md) cho
hợp đồng API, giới hạn biểu thức và phạm vi kiểm chứng.

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

`cuti status` và `GET /api/status` phân loại dữ liệu là `fresh`, `stale` hoặc
`no_data`. Ngưỡng mặc định là 24 giờ và có thể đổi bằng
`CUTI_DATA_STALE_AFTER_HOURS`.

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

Ảnh lot được tách khỏi luồng cào. Crawler chỉ lưu URL vào SQLite; API trả trạng
thái `queued` và không chờ Telegram. Chạy `cuti upload-images --limit 20` ở
process riêng để Telegram tự tải ảnh từ URL bằng `sendPhoto`; máy local không
tải bytes ảnh. Worker commit từng ảnh, in lỗi theo lot/index và trả exit code
khác 0 nếu còn ảnh lỗi để lần chạy sau retry. API không trả URL CDN chứa bot token.
Mỗi cover là snapshot bất biến theo `(lot_id, idx=0)`: URL giống thì idempotent;
URL khác trả conflict, giữ nguyên ảnh và metadata Telegram đã lưu.

### Chạy crawler định kỳ và image worker

Lệnh dùng hằng ngày tại root repo (giữ nguyên DB hiện có):

```powershell
.\.venv\Scripts\python.exe scripts\run_daily.py
```

Lệnh này quản lý crawler và đúng một image worker, đối soát cover còn thiếu của
cả lot hiện tại lẫn lot cũ trong DB, rồi chờ queue xử lý xong và in tổng kết.
Ảnh `ready` được giữ nguyên; job dang dở được phục hồi theo lease/retry hiện có.
Không cần xóa DB, chạy `init-db`, nhập ngày hoặc mở thêm cửa sổ upload ảnh.
Nếu crawler bỏ qua vì dữ liệu còn mới, đối soát ảnh và phục hồi queue vẫn chạy.

Queue rảnh tạm thời không có nghĩa hoàn tất: lệnh vẫn chờ retry đến hạn/lease
hết hạn. Lot không lấy được cover, ảnh lỗi permanent, lỗi crawler/worker đều được
báo rõ và trả exit code khác `0`; không tự đoán URL hoặc thay ảnh của lot khác.
`Ctrl+C` dừng lượt chạy có kiểm soát. Không mở worker riêng đồng thời với lệnh này.

Telegram tự tải URL nguồn qua `sendPhoto`. Có một giới hạn at-least-once: nếu
Telegram đã nhận ảnh nhưng process chết trước khi DB commit, lần phục hồi có thể
gửi trùng một tin nhắn Telegram. Không có bảo đảm exactly-once ở cửa sổ đó.

Verify offline vẫn chạy bằng `scripts/verify.py`. Kiểm tra tiến trình con thật
được tách riêng khỏi tầng offline vì dùng HTTP giả trên loopback:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p daily_process_integration_t2.py -v
```

Harness này dùng DB tạm và credential giả; không gửi dữ liệu mẫu lên Telegram thật.

Các lệnh tách bên dưới vẫn dành cho chẩn đoán hoặc vận hành thủ công:

Scheduled crawler dùng mốc mới nhất của `lots.updated_at` và
`live_watch.last_seen_at`. Nếu dữ liệu còn mới, nó bỏ qua lần chạy; lỗi truy vấn,
timestamp hoặc pipeline in `[ERROR]` và trả exit code `1` để Task Scheduler/cron
không báo thành công giả.

Mở một cửa sổ PowerShell để chạy crawler:

```powershell
.\.venv\Scripts\python.exe scripts\run_scheduled_crawl.py
```

Dùng `--force` khi cần chạy bất kể freshness:

```powershell
.\.venv\Scripts\python.exe scripts\run_scheduled_crawl.py --force
```

Mở một cửa sổ PowerShell khác để chạy worker bền vững:

```powershell
.\.venv\Scripts\python.exe scripts\run_image_worker.py --limit 20 --poll-seconds 30
```

`--limit` là batch tối đa mỗi lượt có việc; `--poll-seconds` chỉ dùng khi hàng
đợi rỗng. Worker lấy timestamp UTC mới ở mỗi lượt, commit từng ảnh qua
`process_lot_image_queue`, và dựa vào lease SQLite hiện có để nhiều process không
nhận cùng một ảnh. Nhấn `Ctrl+C` để dừng sạch. Không có biến môi trường mới; các
giá trị lease, retry, pause và Telegram giữ theo `.env.example`.

### Kiểm tra Details của một lot (smoke test thủ công)

Đường này chỉ tải và parse một trang, không mở kết nối SQLite và không ghi DB:

```text
cuti fetch-lot-details --url https://www.catawiki.com/en/l/123456-example
cuti fetch-lot-details --lot-id 123456
```

Kết quả luôn là JSON gồm các trường Details đã parse được. Để lấy Details trong
`settle` hoặc `ingest-lot`, bật `CUTI_DETAILS_ENABLED=true`; mặc định tắt để các
lệnh verify và chạy offline không gọi mạng.

## Bật dữ liệu thật

Đặt các biến môi trường nguồn thật (không dùng giá trị mẫu), rồi chạy đúng thứ tự:

```powershell
$env:CUTI_LOTS_SOURCE_URL = "https://..."
$env:CUTI_CATAWIKI_API_BASE = "https://www.catawiki.com"
$env:CUTI_DETAILS_ENABLED = "true"
cuti init-db
cuti ingest --max-lots 50
cuti settle
cuti evaluate --query "Omega Seamaster Diver 300M" --cost 1000 --currency eur --condition naked
cuti liquidity
cuti report
cuti status
```

Các biến nguồn cần set là `CUTI_LOTS_SOURCE_URL`, `CUTI_CATAWIKI_API_BASE`,
`CUTI_DETAILS_ENABLED=true`; các biến timeout, giới hạn trang và nhịp gọi giữ theo
`.env.example`. Lưu HTML thật từ trình duyệt vào `tests/fixtures/live/<lot_id>.html`
trước khi chạy verify offline; không ghi đè fixture đã có. Nếu bật Telegram, set
`CUTI_NOTIFIER=telegram`, `CUTI_TELEGRAM_BOT_TOKEN` và `CUTI_TELEGRAM_CHAT_ID`.

`fetch-lot-details` gọi trực tiếp nguồn lot nên chỉ chạy smoke test có kiểm soát,
không gọi trong vòng lặp. `ingest_one_lot` tạo fetcher mới cho từng lot, vì vậy
giới hạn tốc độ chỉ có hiệu lực trong một phiên `settle`.

Hai ngưỡng đủ mẫu vẫn tách biệt: `CUTI_MIN_COMPARABLES` dùng cho verdict theo số
lot đã bán, còn các chỉ số thanh khoản cần tổng số lot trong pool đạt ngưỡng đã nêu
ở trên. Chuỗi thanh khoản bỏ các cửa sổ mỏng; chỉ hiện khi còn ít nhất 2 cửa sổ đủ
mẫu.

Dữ liệu fixture tổng hợp chỉ dùng để kiểm thử; synthetic không bao giờ là nguồn cho
biên lợi nhuận (margin) hoặc pool comparable của dữ liệu thật.
Tầng storage dùng hằng số module `SYNTHETIC_SOURCE = "synthetic_test"`; cả bốn
đường đọc pool (`fetch_lots_for_model`, `fetch_lots_for_liquidity`,
`fetch_sold_lots_since`, `search_sold_lots`) đều bind hằng số này và loại lot
synthetic khỏi pool.

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
- Không tải bytes ảnh về local và không lưu sổ từng lần đấu. SQLite chỉ giữ URL
  cover cùng Telegram metadata; `hearts` và `bids_count` được snapshot khi đóng.
