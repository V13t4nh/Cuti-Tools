# UX Contract

**Phiên bản:** 0.3  
**Ngày chốt:** 2026-08-25  
**Nguồn:** [IA](./IA.md), [Product Search](./features/product-search.md),
[Saved Items](./features/saved-items.md) và
[Auction Lot Discovery](./features/auction-lot-discovery.md), cùng
[Liquidity Market](./features/liquidity-market.md). Luồng đầu-cuối và cách xử lý
cognitive bottlenecks nằm tại [Core Journey: Thẩm định cơ hội mua](./journeys/assessment.md).
Mọi màn hình tuân theo [Global UX Rules](./GLOBAL_UX_RULES.md) và
[Responsive UX Contract](./RESPONSIVE_CONTRACT.md). Chuyển route, tab, detail và popover
tuân theo [Motion Contract](./MOTION_CONTRACT.md).

UX Contract mô tả hành vi mà người dùng có thể quan sát. Nó không quy định framework,
component library hay search engine.

## Nguyên tắc toàn cục

- Giao diện hiển thị số liệu do lõi/backend trả về; frontend không tự tính lại luật nghiệp vụ.
- Thiếu dữ liệu phải hiện **Không đủ dữ liệu**. Không dùng `0`, giá trị mặc định hoặc phỏng đoán để thay dữ liệu thật.
- Lỗi hệ thống, không có kết quả và không đủ dữ liệu là các trạng thái khác nhau.
- Mọi kết luận phải cho người dùng đường kiểm tra cơ sở quyết định và độ mới dữ liệu.
- Ngưỡng dữ liệu cũ lấy từ cấu hình vận hành; frontend không hard-code ngưỡng riêng.
- Không tự lưu hành vi hoặc kết quả thành nội dung của người dùng. Chỉ hành động lưu rõ ràng mới tạo nội dung trong **Theo dõi**.

## Contract điều hướng

- Người dùng bắt đầu quyết định mua tại **Thẩm định**.
- Người dùng quay lại Thương vụ và Mẫu đã lưu tại **Theo dõi**.
- Người dùng xem bối cảnh rộng hơn tại **Thị trường**.
- Frontend có bốn page/route: **Thẩm định**, **Theo dõi**, **Thị trường** và **Cấu hình tính toán**; các nhóm con của ba page đầu dùng tab và detail panel.
- **Cấu hình tính toán** là page vận hành riêng tại `/settings`, không phải tab trong Thẩm định.
- Trạng thái dữ liệu luôn có thể truy cập bằng một popover toàn cục.
- Các dữ liệu so sánh, biên lợi nhuận, rủi ro và bối cảnh thanh khoản của một kết quả nằm trong ngữ cảnh thẩm định đó.
- Tìm sản phẩm, nhập thương vụ và kết quả thẩm định nằm trong cùng một page; người dùng không phải chuyển trang giữa các bước.

## Journey 1: Đánh giá cơ hội mua

### Chuỗi trạng thái

```text
Chưa chọn sản phẩm
  -> Đang tìm / Có đề xuất
  -> Đã xác nhận sản phẩm
  -> Đã nhập đủ thông tin thương vụ
  -> Đang thẩm định
  -> Có kết luận | Không đủ dữ liệu | Lỗi
```

### Xác định sản phẩm

- Ô sản phẩm hoạt động theo [Feature Spec: Product Search](./features/product-search.md).
- Tên đang nằm trong ô nhập không đồng nghĩa với một sản phẩm đã được xác nhận.
- Chỉ thao tác chọn một đề xuất mới thiết lập sản phẩm chuẩn cho lần thẩm định.
- Sửa tên sau khi chọn hủy lựa chọn cũ và làm kết quả thẩm định trước đó hết hiệu lực.

### Thông tin thương vụ

Sau khi xác nhận sản phẩm, người dùng tự nhập:

- giá người bán chào;
- tiền tệ;
- tình trạng đồng hồ.

Không yêu cầu người dùng nhập dáng vỏ khi giá trị đó chưa ảnh hưởng đến kết quả thẩm định.

### Điều kiện được thẩm định

Chỉ cho phép thẩm định khi:

- có sản phẩm chuẩn đã được người dùng xác nhận;
- các trường thương vụ bắt buộc hợp lệ;
- trạng thái dữ liệu không phải **Không có dữ liệu**.

Nếu một điều kiện chưa đạt, giao diện chỉ rõ điều gì còn thiếu và không gửi một yêu cầu thẩm định giả định.

### Kết quả

Kết quả phải giúp người dùng quyết định mua, thương lượng hoặc bỏ qua bằng cách thể hiện:

- kết luận;
- mức giá mua tối đa nếu lõi có thể xác định;
- lý do chính;
- dữ liệu so sánh và mức độ đủ của bằng chứng;
- biên lợi nhuận, rủi ro và bối cảnh thanh khoản khi có dữ liệu.

Khi lõi trả **Không đủ dữ liệu**, giao diện không hiển thị các con số suy diễn như thể đó
là một kết luận hợp lệ.

### Lưu hay không lưu kết quả

- Mặc định, kết quả chỉ phục vụ lần thẩm định hiện tại.
- Không bấm **Lưu thương vụ** thì kết quả không xuất hiện trong lịch sử hoặc khu vực **Theo dõi**.
- Bấm **Lưu mẫu** chỉ lưu sản phẩm; hành động này không lưu kết quả thẩm định.
- Bấm **Lưu thương vụ** tạo một thương vụ ở trạng thái **Đang cân nhắc** và giữ lại bối cảnh quyết định theo [Saved Items](./features/saved-items.md).

## Contract độ mới dữ liệu

- **Fresh:** thẩm định hoạt động bình thường.
- **Stale:** vẫn cho phép thẩm định, nhưng phải cảnh báo rõ dữ liệu đã cũ và cho biết lần cập nhật gần nhất hoặc độ tuổi dữ liệu.
- **No data:** chặn thẩm định và thông báo chưa có dữ liệu thị trường để đưa ra quyết định.

Ngưỡng mặc định hiện tại là 24 giờ và có thể thay đổi bằng cấu hình vận hành.

## Journey 2: Theo dõi nội dung đã lưu

- **Mẫu đã lưu** mở lại hồ sơ sản phẩm với thông tin thị trường mới nhất.
- **Thương vụ** mở lại đúng bối cảnh thẩm định đã lưu.
- Thương vụ dùng vòng đời tối thiểu **Đang cân nhắc → Đã mua | Đã bỏ qua**.
- Không có nội dung nào xuất hiện ở đây nếu người dùng chưa chủ động lưu.

## Journey 3: Khám phá thị trường và lô đấu giá

- Phiên đấu giá dùng một ô search cùng bộ lọc **Tất cả**, **Đang mở**, **Chờ kết quả**.
- Search và filter cập nhật danh sách; chọn một lô mới mở detail.
- Thanh khoản xếp hạng phân khúc theo thương hiệu và dáng vỏ, đồng thời cho search theo thương hiệu và lọc theo xu hướng hoặc tín hiệu Dừng mua.
- Phân khúc không đạt cỡ mẫu tối thiểu hiển thị **Không đủ dữ liệu** và không nhận tín hiệu giả.
- Độ mới và tình trạng nguồn dữ liệu phải hiện diện xuyên suốt hành trình.

## Journey 4: Cấu hình tính toán

- Page **Cấu hình tính toán** hiển thị cấu hình active, revision và nguồn (`env-derived / chưa lưu` hoặc profile file).
- Người dùng có thể chỉnh giá trị và đơn vị của tham số, thêm hoặc xoá tham số custom, thêm hoặc xoá helper, và sửa `net_proceeds` hoặc `profit_threshold`.
- Tên tham số bắt buộc và đơn vị của chúng không được sửa; tham số/helper đang được công thức tham chiếu không bị xoá âm thầm. Backend là nơi xác nhận tham chiếu, cú pháp, đơn vị và điều kiện nghịch đảo.
- Preview yêu cầu hai input mẫu `hammer_eur` và `cost_eur`. UI chỉ gửi draft và hiển thị các trường `formatted` do backend trả về; không tự tính hoặc tự làm tròn.
- Apply chỉ được phép sau preview thành công của đúng draft, input và active revision. Preview/apply lỗi giữ nguyên active config.
- Khi revision đã cũ, UI báo xung đột và yêu cầu tải cấu hình mới rồi xem lại thay đổi trước khi áp dụng.
- Khi draft chưa áp dụng, điều hướng nội bộ và back/forward của trình duyệt phải hỏi xác nhận trước khi bỏ thay đổi; Apply thành công hoặc tải lại cấu hình sẽ tắt cảnh báo.

## Phần ngoài baseline UI hiện tại

- Luồng đề nghị bổ sung sản phẩm khi Product Search không tìm thấy.
- Trích xuất tên đồng hồ từ toàn bộ bài đăng Facebook.

Các phần trên không được tự suy diễn trong UI. Chúng cần được chốt thành feature spec rồi
mới bổ sung vào UX Contract.
