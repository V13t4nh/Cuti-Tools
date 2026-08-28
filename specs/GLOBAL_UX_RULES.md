# Global UX Rules

**Trạng thái:** Baseline toàn dự án đã chốt ngày 2026-08-25.  
**Phạm vi:** Tất cả màn hình frontend dành cho người dùng cuối.

| ID | Khu vực | Global UX Rule |
|---|---|---|
| GUX-01 | Ngôn ngữ | Giao diện dùng tiếng Việt rõ nghĩa; không lộ enum, mã trạng thái hoặc lỗi kỹ thuật cho người dùng. |
| GUX-02 | Thiết bị | Thiết kế desktop-first nhưng desktop, tablet và mobile có feature/content parity 100%. Không có hành động chỉ dùng được bằng hover và không yêu cầu chuyển sang desktop. |
| GUX-03 | Responsive | Breakpoint chỉ thay đổi cách sắp xếp, không được ẩn field, metric, filter, bằng chứng, trạng thái hoặc action. Tuân theo [Responsive UX Contract](./RESPONSIVE_CONTRACT.md). |
| GUX-04 | Accessibility | Mục tiêu WCAG 2.2 AA: dùng được bằng bàn phím, focus nhìn thấy, label gắn với input, thông báo trạng thái được đọc bởi assistive technology và màu sắc không mang nghĩa một mình. |
| GUX-05 | Điều hướng | Frontend chỉ có ba route chính: Thẩm định, Theo dõi và Thị trường. Theo dõi và Thị trường dùng tab nội bộ. Trạng thái dữ liệu là popover toàn cục. Back/forward của trình duyệt phải giữ đúng ngữ cảnh. |
| GUX-06 | Nguồn số liệu | Frontend chỉ hiển thị dữ liệu và kết quả do backend/lõi trả về; không tự tính lại luật nghiệp vụ hoặc tự tạo số thay thế. |
| GUX-07 | Giá trị thiếu | Không hiển thị `null`, `NaN`, vô hạn, ngày mặc định hoặc ô rỗng. Dùng đúng trạng thái **Không có**, **Không áp dụng** hoặc **Không đủ dữ liệu** theo nghĩa dữ liệu. |
| GUX-08 | Loading | Không để màn hình trắng. Giữ khung nội dung ổn định, thể hiện khu vực đang tải và ngăn cùng một hành động được gửi lặp trong lúc xử lý. |
| GUX-09 | Empty | Empty state nói rõ danh sách thực sự chưa có nội dung hay không có kết quả do search/filter; không trộn hai trường hợp. |
| GUX-10 | Error | Lỗi nói điều gì không thực hiện được và hành động tiếp theo. Lỗi field nằm tại field; lỗi tải khu vực nằm tại khu vực; không dùng toast làm nơi duy nhất chứa lỗi. |
| GUX-11 | Feedback | Toast chỉ dùng cho xác nhận ngắn như đã lưu hoặc đã bỏ lưu. Cảnh báo còn hiệu lực nằm inline/banner cho đến khi điều kiện biến mất. |
| GUX-12 | Modal | Không dùng modal cho dữ liệu stale, kết quả chưa lưu hoặc thao tác có thể hoàn tác. Chỉ dùng khi hành động khó phục hồi và hậu quả cần được xác nhận rõ. |
| GUX-13 | Freshness | Fresh không gây nhiễu. Stale hiện cảnh báo cùng lần cập nhật gần nhất nhưng vẫn cho tiếp tục. No data chặn hành động phụ thuộc dữ liệu thị trường. |
| GUX-14 | Insufficient data | **Không đủ dữ liệu** là kết quả nghiệp vụ riêng; không giả thành lỗi và không hiển thị các con số suy diễn. |
| GUX-15 | Form | Validation diễn ra khi rời field hoặc submit; search là ngoại lệ và phản hồi khi nhập. Lỗi không xóa input. Field bắt buộc không được tự điền giá trị nghiệp vụ thay người dùng. |
| GUX-16 | Tiền | Locale hiển thị là `vi-VN`. VND không có phần thập phân; ngoại tệ tối đa hai chữ số thập phân. Mọi số tiền luôn đi cùng mã tiền tệ hoặc ký hiệu không gây nhầm lẫn. |
| GUX-17 | Phần trăm và chỉ số | Phần trăm hiển thị tối đa một chữ số thập phân. Giá trị dùng cho quyết định vẫn giữ nguyên ở backend; mọi màn hình dùng chung một formatter. |
| GUX-18 | Ngày giờ | Ngày dùng `dd/MM/yyyy`; thời điểm dùng `dd/MM/yyyy HH:mm`, múi giờ `Asia/Ho_Chi_Minh`. Độ mới có thể dùng thời gian tương đối nhưng phải mở được thời điểm tuyệt đối. |
| GUX-19 | Product Search | Hiển thị tối đa 10 đề xuất tên chuẩn + reference; exact reference đứng đầu; không tự chọn; sửa nội dung hủy sản phẩm đã xác nhận và kết quả phụ thuộc nó. |
| GUX-20 | List Search | Search trong danh sách cập nhật chính danh sách đó. Một kết quả vẫn không tự mở detail. Search và filter có thể dùng đồng thời và có cách xóa điều kiện rõ ràng. |
| GUX-21 | Kết quả thẩm định | Thứ tự đọc bắt buộc: Kết luận → Mức mua tối đa → Khoảng cách với giá chào → Lý do chính → Bằng chứng chi tiết. Không dùng màu mà thiếu nhãn chữ. |
| GUX-22 | Invalidation | Khi input ảnh hưởng kết quả bị thay đổi, kết quả cũ hết hiệu lực ngay; không để người dùng hành động trên kết quả của input trước đó. |
| GUX-23 | Persistence | Không tự lưu thẩm định, mẫu, thương vụ, search hay filter. Chỉ hành động rõ ràng của người dùng mới tạo nội dung trong Theo dõi. |
| GUX-24 | Saved Items | **Lưu mẫu** nằm gần định danh sản phẩm. **Lưu thương vụ** nằm tại kết quả. Phản hồi sau lưu phải nói chính xác thứ được lưu và thứ chưa được lưu. |
| GUX-25 | Unsaved result | Kết quả chưa lưu phải có nhãn **Chưa lưu**. Rời màn hình không tạo lịch sử và không bật modal cản trở. |
| GUX-26 | Idempotency | Một hành động đang xử lý không nhận submit trùng. Thử lại cùng dữ liệu không được tạo bản ghi hoặc thay đổi trạng thái ngoài ý muốn. |
| GUX-27 | Detail | Detail thương vụ, mẫu, phân khúc và lô mở trong một panel bên phải của page hiện tại. Đóng panel trở lại đúng danh sách, search và filter trước đó; link nguồn ngoài được phân biệt rõ. |
| GUX-28 | YAGNI | Không thêm onboarding, wizard, advanced filters, saved search, dashboard tùy chỉnh, animation trang trí hoặc hệ thống trợ giúp riêng trước khi có nhu cầu đã quan sát được. |
| GUX-29 | Motion | Chuyển route, tab, detail và popover tuân theo [Motion Contract](./MOTION_CONTRACT.md). Motion tạo continuity, không thay loading state, không cản tương tác và phải hỗ trợ reduced motion. |

## Quy ước trạng thái màu

- Xanh luôn đi cùng nhãn hành động tích cực.
- Vàng luôn đi cùng lý do cần thận trọng.
- Đỏ luôn đi cùng lý do không nên tiếp tục hoặc hành động bị chặn.
- Xám chỉ dùng cho trung tính/không áp dụng, không dùng để che dữ liệu bị thiếu.
