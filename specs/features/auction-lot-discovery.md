# Feature Spec: Auction Lot Discovery

**Trạng thái:** Baseline YAGNI đã chốt ngày 2026-08-25.

## Mục tiêu người dùng

Giúp người dùng tìm một lô cụ thể khi đã biết mình cần gì và đồng thời xem được toàn bộ
lô theo trạng thái công việc hiện tại.

## Hành vi đã chốt

- Phiên đấu giá là một khu vực duy nhất; trạng thái lô không tạo thành các trang riêng.
- Khi chưa nhập search, người dùng vẫn thấy danh sách lô phù hợp với bộ lọc hiện tại.
- Search hỗ trợ tên đồng hồ, reference hoặc mã lô.
- Bộ lọc trạng thái tối thiểu gồm **Tất cả**, **Đang mở** và **Chờ kết quả**.
- Search và bộ lọc trạng thái có thể dùng cùng nhau.
- Kết quả được hiển thị thành danh sách. Người dùng chọn một kết quả để mở chi tiết lô.
- Hệ thống không tự chuyển thẳng đến detail chỉ vì hiện có một kết quả.
- Lô đã kết thúc trở thành dữ liệu so sánh; phiên bản này không tạo một khu vực lịch sử đấu giá riêng.

## Trạng thái quan sát được

- **Có danh sách:** hiển thị các lô thỏa search và bộ lọc.
- **Không có kết quả:** thông báo rõ không có lô phù hợp; không tự nới điều kiện tìm kiếm.
- **Lỗi:** phân biệt lỗi tải dữ liệu với danh sách rỗng.

## Ranh giới ảnh lot

- Phạm vi chấp nhận hiện tại là **tối đa một ảnh cover cho mỗi lot**. Nếu nguồn không
  cung cấp ảnh, lot vẫn được giữ và UI phải hiện rõ trạng thái **Không có ảnh**; hệ thống
  không đoán URL hoặc dùng ảnh thay thế.
- Tính năng gallery đầy đủ của Catawiki được để dành: phát hiện **N ảnh theo đúng thứ tự**, lưu trữ các ảnh đó vào Telegram, UI **See all photos**, và các quy tắc về tính đầy đủ hoặc hàng đợi.
- Luồng chạy hằng ngày, đối soát cover thiếu và phục hồi queue sau crash được chốt
  riêng tại [Daily crawl and image recovery](./daily-crawl-and-images.md).

## Ngoài phạm vi phiên bản này

- Advanced filters hoặc faceted search.
- Saved search và query language.
- Search toàn hệ thống từ một ô chung.
- Tự mở detail khi chỉ còn một kết quả.
- Một trang lịch sử riêng cho toàn bộ lô đã kết thúc.
