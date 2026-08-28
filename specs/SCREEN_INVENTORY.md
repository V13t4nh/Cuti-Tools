# Page Inventory and UI Readiness

**Trạng thái:** Baseline tinh gọn đã chốt ngày 2026-08-25.

## App Shell

Mọi page dùng chung:

- top navigation gồm **Thẩm định**, **Theo dõi**, **Thị trường**, **Cấu hình tính toán**;
- chỉ một mục navigation ở trạng thái active;
- tiện ích độ mới dữ liệu ở góc phải; bấm để mở data popover;
- không dùng sidebar, dashboard home hoặc route trung gian.

## Bốn page chính

| Route | Page | Nội dung |
|---|---|---|
| `/assessment` | Thẩm định | Product Search, input thương vụ, trạng thái dữ liệu, kết quả và hành động lưu trên cùng một page |
| `/tracking` | Theo dõi | Hai tab **Thương vụ** và **Mẫu đã lưu**; detail mở trong panel bên phải |
| `/market` | Thị trường | Hai tab **Thanh khoản** và **Phiên đấu giá**; detail mở trong panel bên phải |
| `/settings` | Cấu hình tính toán | Chỉnh tham số, helper, công thức pricing; chạy preview và áp dụng theo revision |

Route có thể được đặt tên khác khi triển khai, nhưng không được tăng số page chỉ để tách
form, result, list hoặc detail. Cấu hình tính toán là page vận hành riêng theo IA.

## Tab và panel

| Page | Tab | Nội dung danh sách | Detail panel |
|---|---|---|---|
| Theo dõi | Thương vụ | Search và các trạng thái Đang cân nhắc, Đã mua, Đã bỏ qua | Bối cảnh đã lưu, kết quả, dữ liệu hiện tại và cập nhật trạng thái |
| Theo dõi | Mẫu đã lưu | Search mẫu theo tên/reference | Hồ sơ chuẩn, thị trường mới nhất và hành động bắt đầu thẩm định |
| Thị trường | Thanh khoản | Search thương hiệu, lọc xu hướng và bảng xếp hạng | Chỉ số, xu hướng, cỡ mẫu và tín hiệu Dừng mua |
| Thị trường | Phiên đấu giá | Search tên/reference/mã lô và lọc trạng thái | Thông tin lô, sản phẩm được nhận diện, nguồn và hành động thẩm định |

Toàn app dùng một pattern detail panel. Mỗi thời điểm chỉ mở một panel. Đóng panel giữ
nguyên tab, search, filter và vị trí danh sách.

## Data popover

Tiện ích toàn cục hiển thị một trong ba trạng thái **Fresh**, **Stale**, **No data**.
Bấm vào mở popover chứa:

- lần cập nhật gần nhất;
- ngưỡng stale;
- tổng độ phủ dữ liệu;
- tình trạng từng nguồn;
- lỗi nguồn nếu có.

Popover không trở thành page hoặc dashboard riêng.

## Bản đồ chức năng

| Chức năng | Điểm vào | Điểm ra / hành động tiếp theo |
|---|---|---|
| Product Search | Page Thẩm định | Xác nhận sản phẩm rồi nhập thương vụ |
| Thẩm định | Page Thẩm định | Xem kết quả tạm thời, Lưu mẫu hoặc Lưu thương vụ |
| Mẫu đã lưu | Theo dõi → Mẫu đã lưu | Mở detail hoặc bắt đầu thẩm định mẫu đó |
| Thương vụ | Theo dõi → Thương vụ | Xem lại, chuyển Đã mua hoặc Đã bỏ qua |
| Thanh khoản | Thị trường → Thanh khoản | Mở detail phân khúc để hiểu xu hướng/rủi ro |
| Lô đấu giá | Thị trường → Phiên đấu giá | Mở detail, xem nguồn hoặc đưa lô vào Thẩm định |
| Trạng thái dữ liệu | App shell | Hiểu độ tin cậy rồi tiếp tục hoặc dừng hành động phụ thuộc dữ liệu |

Không có chức năng người dùng cuối nào trong IA bị ẩn ngoài ba page trên.

## State Coverage bắt buộc

| State | Thẩm định | Theo dõi | Thị trường | Cấu hình tính toán | Data popover |
|---|:---:|:---:|:---:|:---:|:---:|
| Initial/loading | ✓ | ✓ | ✓ | ✓ | ✓ |
| Loaded/content | ✓ | ✓ | ✓ | ✓ | ✓ |
| Empty | — | ✓ | ✓ | ✓ | — |
| No search results | ✓ | ✓ | ✓ | — | — |
| Validation error | ✓ | ✓ | — | ✓ | — |
| Insufficient data | ✓ | ✓ | ✓ | — | ✓ |
| Stale | ✓ | ✓ | ✓ | ✓ | ✓ |
| No data | ✓ | ✓ | ✓ | — | ✓ |
| System/source error | ✓ | ✓ | ✓ | ✓ | ✓ |
| Unsaved/saved feedback | ✓ | ✓ | — | ✓ | — |

## Build Readiness

| Khu vực | UX/UI baseline | Backend integration hiện tại |
|---|---|---|
| App shell và data popover | Implemented | Status, freshness, coverage và source state đã nối dữ liệu thật |
| Thẩm định | Implemented | Canonical Product Search và Evaluate typed đã nối end-to-end, không có default input nghiệp vụ |
| Theo dõi | Implemented | Saved Product và Tracked Deal persistence/idempotency/lifecycle đã nối SQLite |
| Thanh khoản | Implemented | List/search/filter/detail, data window và nhóm Không đủ dữ liệu đã nối lõi |
| Phiên đấu giá | Implemented | List/search/filter/detail và hai trạng thái công việc đã nối `live_watch` |
| Cấu hình tính toán | Implemented | Đọc active profile, sửa draft, preview/apply qua pricing-config API; không tính toán ở client |

Các page được triển khai trong `frontend/` bằng Vue 3 + TypeScript + Vite và chỉ đọc API
thật. Catalog canonical có provenance trong `config/catalog.json`; fixture không nằm trên
production path. Streamlit nằm ngoài frontend sản phẩm.

Mỗi page, tab, panel và popover phải có đủ feature/content trên desktop, tablet và mobile
theo [Responsive UX Contract](./RESPONSIVE_CONTRACT.md). Responsive version không phải một
scope phụ được phép làm sau.

Route, tab, panel và popover phải triển khai motion ngay trong baseline theo
[Motion Contract](./MOTION_CONTRACT.md); transition không phải polish tùy chọn làm sau.
