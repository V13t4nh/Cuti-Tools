# Feature Spec: Saved Items

**Trạng thái:** Baseline YAGNI đã chốt ngày 2026-08-25.

## Mục tiêu người dùng

Cho phép người dùng quay lại đúng mẫu đồng hồ hoặc thương vụ mà họ đã chủ động chọn lưu,
trong khi các lần thẩm định thông thường vẫn không tạo lịch sử ngoài ý muốn.

## Nguyên tắc không lưu mặc định

- Chạy thẩm định chỉ tạo kết quả để xem trong luồng hiện tại.
- Nếu người dùng không bấm hành động lưu, hệ thống không tạo Mẫu đã lưu, không tạo Thương vụ và không đưa kết quả vào lịch sử người dùng.
- Rời khỏi kết quả không được âm thầm biến nó thành nội dung đã lưu.
- Hai hành động lưu là độc lập và phải được người dùng chủ động thực hiện.

## Mẫu đã lưu

### Hành động

Người dùng bấm **Lưu mẫu** tại nơi đang xem một sản phẩm chuẩn.

### Kết quả

- Mẫu xuất hiện trong **Theo dõi → Mẫu đã lưu**.
- Người dùng có thể mở lại đầy đủ hồ sơ sản phẩm chuẩn.
- Thông tin thị trường hiển thị khi mở lại là thông tin mới nhất, không phải một bản chụp cũ tại thời điểm lưu.
- Bỏ lưu sẽ loại mẫu khỏi danh sách của người dùng nhưng không xóa sản phẩm chuẩn hoặc dữ liệu thị trường.

Lưu mẫu không tự lưu kết quả thẩm định và không tự tạo thương vụ.

## Thương vụ

### Hành động

Sau khi có kết quả thẩm định, người dùng có thể bấm **Lưu thương vụ**.

### Kết quả

Thương vụ lưu lại bối cảnh quyết định tại thời điểm đó:

- sản phẩm chuẩn;
- giá người bán chào, tiền tệ và tình trạng đồng hồ;
- kết luận và mức giá mua tối đa nếu có;
- bằng chứng đã dùng và mức độ đủ dữ liệu;
- độ mới dữ liệu;
- thời điểm thẩm định.

Thương vụ xuất hiện trong **Theo dõi → Thương vụ** với trạng thái ban đầu **Đang cân nhắc**.

### Vòng đời tối thiểu

```text
Đang cân nhắc -> Đã mua
Đang cân nhắc -> Đã bỏ qua
```

**Lưu thương vụ** nghĩa là bắt đầu theo dõi. **Đã mua** chỉ dùng khi giao dịch thực sự đã chốt.

## Ngoài phạm vi phiên bản này

- Tự động lưu mọi lần thẩm định.
- Thư mục, tag hoặc danh sách tùy chỉnh.
- Reminder và notification do người dùng cấu hình.
- Ghi chú, tệp đính kèm hoặc cộng tác nhiều người.
- Pipeline trạng thái tùy chỉnh.
- Lưu một bản chụp thị trường riêng cho Mẫu đã lưu.

