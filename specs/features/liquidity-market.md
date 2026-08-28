# Feature Spec: Liquidity Market

**Trạng thái:** Baseline YAGNI đã chốt ngày 2026-08-25.

## Mục tiêu người dùng

Giúp người dùng nhận biết phân khúc đồng hồ nào đang dễ bán, đang suy giảm hoặc đã phát
tín hiệu dừng mua trước khi phân bổ vốn.

## Đơn vị phân khúc

Mỗi phân khúc là một cặp **Thương hiệu + Dáng vỏ**. Dáng vỏ là metadata thị trường trong
feature này; nó không trở thành input bắt buộc của luồng thẩm định.

## Tổng quan thanh khoản

- Danh sách mặc định xếp theo Liquidity Index từ cao xuống thấp.
- Mỗi phân khúc hiển thị tối thiểu:
  - thương hiệu và dáng vỏ;
  - Liquidity Index;
  - số lô và số lô bán được;
  - sell-through rate;
  - median days to close nếu đủ dữ liệu;
  - trạng thái **Cải thiện**, **Ổn định** hoặc **Suy giảm**;
  - tín hiệu **Dừng mua** khi lõi đã xác định.
- Người dùng có thể search theo thương hiệu.
- Bộ lọc tối thiểu gồm **Tất cả**, **Cải thiện**, **Ổn định**, **Suy giảm** và **Dừng mua**.
- Search và filter dùng đồng thời.
- Chọn một phân khúc mở detail; quay lại giữ nguyên search/filter.

## Chi tiết phân khúc

Detail trình bày theo thứ tự:

1. Trạng thái và tín hiệu Dừng mua.
2. Liquidity Index và thay đổi quý gần nhất.
3. Sell-through, tốc độ bán, median days to close và heart-to-hammer.
4. Cỡ mẫu và khoảng thời gian dữ liệu.
5. Giải thích dữ liệu đủ hay chưa đủ để đưa ra tín hiệu.

Nếu một phân khúc không đạt cỡ mẫu tối thiểu, nó không được xếp hạng như một phân khúc
hợp lệ. Khi được tìm thấy, nó hiển thị **Không đủ dữ liệu**, số lô hiện có và không có tín hiệu giả.

## Trạng thái dữ liệu

- Stale: vẫn cho xem và lọc nhưng cảnh báo toàn khu vực.
- No data: không hiển thị bảng rỗng như thể không có phân khúc; thông báo chưa có dữ liệu thị trường.
- Lỗi: phân biệt với No data và cung cấp hành động thử lại.

## Ngoài phạm vi phiên bản này

- Chọn khoảng thời gian tùy ý.
- So sánh nhiều phân khúc trong một chart tùy chỉnh.
- Tự đặt trọng số Liquidity Index.
- Export dashboard, saved filter hoặc alert theo phân khúc.
- Lưu phân khúc thành một loại Saved Item mới.

