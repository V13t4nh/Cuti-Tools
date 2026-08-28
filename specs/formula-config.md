# Pricing formula configuration v1

**Trạng thái:** kế hoạch implementation đã được Lead duyệt ngày 2026-08-28,
theo yêu cầu người dùng ngày 2026-08-28. Đây là nguồn phạm vi cho implementation.

## Mục tiêu và phạm vi

Cho phép người vận hành thay đổi các tham số chi phí và một số công thức pricing từ
giao diện, sau đó xem thử kết quả trước khi áp dụng. Pricing vẫn được tính một lần ở
backend dùng chung cho API, CLI và các pipeline hiện có. Frontend chỉ sửa bản nháp,
gửi preview/apply và hiển thị giá trị backend trả về.

V1 chỉ cấu hình pricing: `net_proceeds`, `profit_threshold`, các tham số phí, tỷ giá,
biên lợi nhuận và khoản EUR/rate bổ sung do user khai báo. Bắt buộc expose các tham số
`commission_rate`, `vat_on_commission_rate`, `shipping_eur`, `eur_vnd_rate`,
`min_margin_rate`, `min_profit_eur`; `min_comparables` không
được đưa lên UI vì thuộc ngưỡng matching/data sufficiency. Matching/similarity,
percentile, verdict, currency conversion và liquidity vẫn giữ luật hiện tại.
`liquidity.py:56-72` là một hệ công thức khác, không đưa vào cùng editor trong lượt này.

Không đổi hoặc xoá ba route hiện có (`/assessment`, `/tracking`, `/market`). Thêm route
`/settings` cho workspace cấu hình; quyền truy cập giữ nguyên mô hình local hiện tại,
không thêm hệ thống auth.

## Công thức và biến được phép

Hai output bắt buộc có đúng tên `net_proceeds` và `profit_threshold`; output đều là
EUR. Có thể khai báo helper có tên duy nhất. Helper được phụ thuộc vào tham số, input
runtime hoặc helper khác nếu đồ thị là DAG và toàn bộ biểu thức qua kiểm tra domain/
affine bên dưới.

Ví dụ mặc định tương đương code hiện tại:

```text
net_proceeds = hammer_eur - hammer_eur * commission_rate * (1 + vat_on_commission_rate) - shipping_eur - cost_eur
profit_threshold = max(cost_eur * min_margin_rate, min_profit_eur)
```

Syntax được hỗ trợ:

- số thập phân hữu hạn, tên biến snake_case, `+`, `-`, `*`, `/`, unary `+/-`, ngoặc;
- `min(a, b, ...)` và `max(a, b, ...)` là hai built-in duy nhất, có ít nhất hai đối số;
- không có Python code, import, attribute, indexing, string, comparison, conditional,
  exponent, modulo hoặc function call khác.

Tên biến phải tồn tại trong profile hoặc là input hệ thống. Giá trị phải hữu hạn;
chia cho 0, biến thiếu, helper cycle và kết quả không hữu hạn đều là lỗi có kiểu.
Mỗi tham số có đơn vị bắt buộc. V1 dùng `eur` cho các khoản tiền trong công thức,
`rate` cho tỷ lệ và `vnd_per_eur` cho tỷ giá; phép cộng/trừ chỉ cùng đơn vị,
phép nhân/chia phải tạo ra đơn vị hợp lệ. Chi phí mới muốn thêm phải khai báo tham số
EUR rồi được tham chiếu rõ trong `net_proceeds`; xoá tham số đang được tham chiếu bị
từ chối.

## Điều kiện để giữ giá nghịch đảo đúng

Không dùng generic solver và không chấp nhận công thức chỉ vì parse được.

- Sau khi thay helper và tham số, `net_proceeds` phải rút gọn được thành
  `a * hammer_eur + b * cost_eur + c`, với `a > 0` và `b < 0`. `min/max` được parse
  chung nhưng không được bao quanh biểu thức chứa `hammer_eur` hoặc `cost_eur` trong
  output này.
- `profit_threshold` không được dùng `hammer_eur` và phải chứng minh được đơn điệu
  không giảm theo `cost_eur` trên toàn miền cost không âm, không chỉ bằng một sample.
  V1 cho phép dạng hiện tại: `min/max` của các nhánh affine theo cost với hệ số không
  âm.
- `profit_threshold(cost)` phải không âm với mọi `cost >= 0`, và giá trị tại cost
  bằng 0 phải lớn hơn hoặc bằng hằng số `c` của `net_proceeds`. Điều này bảo đảm
  miền break-even không có giá âm; giá bằng 0 vẫn là kết quả hợp lệ nếu công thức
  thực sự cho ra 0.
- Khi hợp lệ, break-even được suy ra từ hệ số affine của `net_proceeds`, còn
  `max_buy_cost_vnd` tiếp tục binary-search vì GREEN vẫn đơn điệu theo cost. Công thức
  làm mất các điều kiện trên bị từ chối với lỗi `unsupported_inverse`; không ẩn số sai.

`break_even_hammer` hiện đang giả định affine tại `src/cuti/pricing.py:107-114`, còn
`max_buy_cost_vnd` giả định predicate GREEN đơn điệu tại `src/cuti/price_limit.py:10-40`.

## Nguồn cấu hình và trạng thái

`config/pricing.json` là profile active, không thêm bảng hoặc cột DB. File chứa
`revision`, `updated_at` (metadata UI, có thể null khi env-derived), `parameters`,
`helpers`, `formulas`. `revision` chính là SHA-256 canonical content hash, gồm 64 ký
tự hex thường, không có tiền tố `sha256:` hoặc field hash riêng.

Khi file chưa tồn tại, profile được dựng một lần trong memory từ các giá trị hiệu lực
của env/default hiện tại (`CUTI_COMMISSION_RATE`, `CUTI_VAT_ON_COMMISSION_RATE`,
`CUTI_SHIPPING_EUR`, `CUTI_EUR_VND_RATE`, `CUTI_MIN_MARGIN_RATE`,
`CUTI_MIN_PROFIT_EUR`). `eur_vnd_rate` giữ vai trò `vnd_per_eur` và thuật toán quy đổi
tiền tệ vẫn nằm trong core, không cho user thay bằng formula. Giao diện phải hiển thị rõ
`env-derived / chưa lưu`; thao tác Apply mới ghi file. Khi file đã tồn tại, nó là
nguồn authoritative cho các field pricing. File đã tồn tại nhưng sai schema/công thức
phải fail sớm; không âm thầm quay về env.

Mỗi request hoặc run nạp đúng một profile bất biến ở đầu và dùng profile đó cho toàn
bộ evaluation, preview, max-buy, status và response. Chỉ một process
`ThreadingHTTPServer` được phép ghi; process-local apply lock bảo vệ chuỗi
read-check-write. Apply validate toàn candidate trước khi ghi, ghi file tạm cùng thư
mục rồi atomic replace; nếu apply lỗi thì profile active hợp lệ vẫn nguyên vẹn.
`expected_revision` bắt buộc khi Apply; mismatch trả conflict và không ghi đè bản mới
hơn. Preview không ghi file, không tăng revision. CLI/pipelines chỉ đọc profile.

Mỗi quote/deal mới phải nhúng một `pricing_profile` đầy đủ gồm revision (canonical
content hash), tham số, helper và expression đã dùng vào JSON hiện có
(`quotes.assumptions` và `tracked_deals.snapshot_json`). Backend phải kiểm tra
revision là canonical hash đúng với chính nội dung profile trong snapshot; không bắt snapshot phải khớp
revision active hiện tại, vì kết quả đã tính trước đó vẫn phải lưu được sau khi
người vận hành đổi config. Snapshot thiếu hoặc tự mâu thuẫn bị từ chối; các dòng
legacy đã lưu không bị sửa và kết quả lịch sử không được tự tính lại theo profile mới.

## API contract tối thiểu

`GET /api/pricing-config` và response thành công của `PUT` dùng đúng shape:

```json
{
  "state": "active",
  "active": {
    "revision": "<64 lowercase hex characters>",
    "source": "env-derived|file",
    "updated_at": null,
    "parameters": [{"name": "shipping_eur", "value": 35, "unit": "eur", "required": true, "removable": false}],
    "helpers": [{"name": "total_fee_multiplier", "expression": "commission_rate * (1 + vat_on_commission_rate)"}],
    "formulas": {"net_proceeds": "...", "profit_threshold": "..."},
    "input_variables": [{"name": "hammer_eur", "unit": "eur", "source": "system"}, {"name": "cost_eur", "unit": "eur", "source": "system"}],
    "capabilities": {"net_proceeds": {"valid": true, "inverse": "affine"}, "profit_threshold": {"valid": true, "inverse": "monotone"}}
  }
}
```

`POST /api/pricing-config/preview` nhận `{ "draft": {"parameters": [...],
"helpers": [...], "formulas": {...}}, "inputs": {"hammer_eur": 1000,
"cost_eur": 200} }` và trả `{ "valid": true|false, "active_revision": "...",
"draft": {...}, "preview": {"outputs": [{"name": "net_proceeds", "label":
"...", "value": 0, "unit": "eur", "formatted": "..."}], "active_outputs":
[...]}, "errors": [{"field": "...", "code": "...", "message": "..."}] }`.
Khi hợp lệ, outputs tối thiểu gồm `net_proceeds`, `profit_threshold`,
`break_even_hammer`; `active_outputs` phục vụ so sánh trước/sau, không để frontend tự
tính. Preview không mutate state.

`PUT /api/pricing-config` nhận `{ "expected_revision": "...", "draft":
{"parameters": [...], "helpers": [...], "formulas": {...}} }`. Thành công trả đúng
shape GET với profile active mới. Lỗi validation trả HTTP 422 cùng `errors`; revision
cũ trả HTTP 409 với `stale_revision`. Không có apply một phần.

HTTP JSON phải là JSON nghiêm ngặt: request chứa `NaN`, `Infinity`, `-Infinity`,
số vượt giới hạn hữu hạn hoặc giá trị trung gian/kết quả không hữu hạn đều bị từ
chối bằng lỗi có kiểu. Response không bao giờ serialize các giá trị đó thành token
JSON không chuẩn.

## UI contract

UI có draft tách khỏi active profile, hiển thị đơn vị và biến được phép, nút Preview và
Apply, lỗi tại field/formula, revision active và thông báo áp dụng thành công. Không tự
tính hoặc tự làm tròn kết quả. Bản nháp sai không được thay thế active config; khi có
stale revision phải yêu cầu tải profile mới rồi xem lại thay đổi.

## Ownership và verification

- Backend/config: profile model, parser/evaluator whitelist, unit/affine/monotonic
  validation, atomic store, revision conflict, API và snapshot integration. Chỉ vùng
  `src/cuti/config*`, pricing/config storage và API contract mới thuộc write scope;
  không sửa matching hoặc liquidity.
- Frontend: `/settings`, draft/preview/apply/error và API types; không chứa công thức
  nghiệp vụ. IA/Screen Inventory/UX Contract là write scope frontend trước implementation.
- QA/Verification: test syntax, units, cycles, division/non-finite, default parity,
  inverse rejection, stale apply, atomic failure, preview no-write và snapshot. Test
  mới do người nghiệm thu chốt; không nới test hiện có.

Lệnh kiểm tra hẹp sau implementation: `make test`, rồi cổng repo `make verify`.
Tầng UI cần một browser smoke/isolated fixture cho `/settings`, preview/apply,
stale-revision và không lộ giá trị rỗng; fixture phải được test offline đọc lại.
Không thêm dependency; `pyproject.toml` hiện khai báo `dependencies = []`.

## Tài liệu cần cập nhật trước khi triển khai

Đây là feature mới chưa có trong baseline UX. Frontend phải update [IA.md](IA.md),
[SCREEN_INVENTORY.md](SCREEN_INVENTORY.md) và [UX_CONTRACT.md](UX_CONTRACT.md) để
thêm `/settings`; `notion.md` cần ghi nhận artifact và tiêu chí nghiệm thu. Các kiểm
tra acceptance trực tiếp cho snapshot canonical, HTTP JSON strictness và browser
`/settings` vẫn phải chạy; tài liệu này không coi feature là hoàn tất chỉ vì
unit/build xanh. User permission cho test mới vẫn do Lead xin trước khi QA viết test.
