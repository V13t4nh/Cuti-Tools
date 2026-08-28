# Feature Spec: Product Search

**Trạng thái:** Baseline đã chốt ngày 2026-08-25.

## Mục tiêu người dùng

Giúp người dùng xác định đúng mẫu đồng hồ chuẩn trước khi chạy thẩm định, ngay cả khi họ
chỉ nhớ hoặc chỉ nhập được một phần tên sản phẩm.

## Hành vi đã chốt

1. Người dùng nhập tên đầy đủ hoặc một phần tên đồng hồ vào một ô tìm kiếm.
2. Khi có nội dung, hệ thống hiển thị tối đa 10 sản phẩm gần nhất ngay bên dưới ô nhập.
3. Mỗi đề xuất hiển thị tên chuẩn và mã reference nếu có để người dùng phân biệt các mẫu gần giống nhau.
4. Kết quả được ưu tiên theo thứ tự:
   - reference khớp chính xác;
   - tên hoặc model chuẩn khớp chính xác;
   - alias đã được xác nhận;
   - tên văn bản gần đúng.
5. Không áp dụng sửa sai gần đúng cho reference dạng chữ và số. Reference sai không được biến thành một reference khác chỉ vì trông gần giống.
6. Hệ thống không tự chọn kết quả đầu tiên. Người dùng phải chủ động chọn một đề xuất.
7. Khi người dùng chọn, tên chuẩn được điền lại vào chính ô nhập và hệ thống giữ định danh chuẩn của sản phẩm ở phía sau.
8. Nếu người dùng sửa nội dung sau khi đã chọn, lựa chọn cũ mất hiệu lực và phải được xác nhận lại.
9. Không được chạy thẩm định khi chưa có một sản phẩm đã được xác nhận.
10. Nếu không có kết quả, hệ thống hiển thị rõ **Không tìm thấy sản phẩm phù hợp** và không tự đoán sản phẩm thay người dùng.
11. Nếu dịch vụ tìm kiếm gặp lỗi, giao diện phải phân biệt lỗi hệ thống với trạng thái không có kết quả.

## Các giá trị người dùng nhập sau khi chọn sản phẩm

- Giá người bán chào.
- Tiền tệ.
- Tình trạng đồng hồ.

`WatchForm` (dáng vỏ) không phải trường bắt buộc của luồng thẩm định tại phiên bản này.
Nó có thể là metadata của sản phẩm chuẩn, nhưng chỉ được đưa thành input khi có luật nghiệp
vụ đã chốt và giá trị đó thực sự làm thay đổi kết quả.

## Trạng thái quan sát được

- **Chưa nhập:** chưa hiển thị đề xuất hoặc lỗi.
- **Đang tìm:** cho biết hệ thống đang xử lý nội dung vừa nhập.
- **Có đề xuất:** hiển thị tối đa 10 lựa chọn.
- **Đã chọn:** ô nhập mang tên chuẩn và có một sản phẩm chuẩn đã được xác nhận.
- **Không có kết quả:** thông báo không tìm thấy, không có lựa chọn ngầm.
- **Lỗi:** thông báo tìm kiếm không khả dụng; không giả thành trạng thái không có kết quả.

## Tiêu chí nghiệm thu hành vi

- Một truy vấn khớp reference chính xác đưa đúng sản phẩm lên đầu.
- Một tên viết chưa chính xác vẫn có thể trả về tối đa 10 tên gần đúng để người dùng tự chọn.
- Chưa chọn đề xuất thì không thể chạy thẩm định.
- Chọn đề xuất sẽ điền tên chuẩn vào ô và giữ đúng định danh sản phẩm.
- Sửa tên sau khi chọn sẽ hủy định danh cũ và vô hiệu hóa việc thẩm định cho đến khi chọn lại.
- Không có kết quả thì không có sản phẩm nào được tự chọn.
- Lỗi dịch vụ và không có kết quả là hai trạng thái khác nhau đối với người dùng.

## Ngoài phạm vi phiên bản này

- Tự động xác nhận sản phẩm mà không cần người dùng chọn.
- Vector search hoặc semantic search.
- Trích xuất tự động tên sản phẩm từ toàn bộ nội dung một bài đăng Facebook.
- Định giá hoặc tính toán quyết định ngay bên trong kết quả tìm kiếm.
- Dùng các lô đấu giá riêng lẻ làm danh mục sản phẩm chuẩn.

## Ranh giới triển khai

Feature spec này không khóa công nghệ search engine. Dù dùng engine nào, danh mục sản phẩm
chuẩn vẫn là nguồn sự thật; search index chỉ là bản đọc có thể dựng lại. Quyết định công
nghệ phải được ghi riêng và không được làm thay đổi các hành vi phía trên.
