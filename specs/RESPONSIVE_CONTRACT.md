# Responsive UX Contract

**Trạng thái:** Baseline đã chốt ngày 2026-08-25.  
**Nguyên tắc:** Responsive thay đổi bố cục, không thay đổi khả năng của sản phẩm.

## Feature và content parity

- Desktop, tablet và mobile có cùng chức năng, nội dung, trạng thái dữ liệu và hành động.
- Không dùng breakpoint để ẩn field, metric, filter, bằng chứng, trạng thái hoặc action.
- Không thay một chức năng bằng bản rút gọn trên mobile.
- Không yêu cầu người dùng chuyển sang desktop để hoàn thành bất kỳ core journey nào.
- Một element có thể đổi vị trí, xuống dòng, chuyển từ table row thành record stack hoặc mở trong sheet; nó không được biến mất.

## Breakpoint behavior

| Viewport | Bố cục |
|---|---|
| Desktop `>= 1200px` | Content rộng, list và detail panel có thể hiển thị cạnh nhau |
| Tablet `768–1199px` | Một hoặc hai cột tùy nội dung; detail panel phủ một phần lớn chiều rộng |
| Mobile `320–767px` | Một cột; detail panel thành full-screen sheet; mọi action và dữ liệu vẫn còn đủ |

Breakpoint có thể được tinh chỉnh trong implementation nếu thiết bị thực tế yêu cầu,
nhưng không được thay đổi nguyên tắc parity.

## App shell

### Desktop và tablet

- Top navigation luôn hiển thị đủ **Thẩm định**, **Theo dõi**, **Thị trường**.
- Trạng thái dữ liệu luôn hiện ở góc phải.

### Mobile

- Top bar luôn hiện tên CUTI và trạng thái dữ liệu.
- Ba navigation item luôn hiện trong bottom navigation; không đặt trong hamburger menu.
- Bottom navigation không che content hoặc primary action.

## Page behavior

### Thẩm định

- Product Search, giá, tiền tệ, tình trạng, kết quả và hành động lưu nằm trong cùng page ở mọi viewport.
- Mobile xếp field theo một cột; giá và tiền tệ có thể nằm cùng hàng khi vẫn đọc và chạm được.
- Autocomplete dùng toàn chiều rộng khả dụng và mọi đề xuất đều truy cập được bằng cuộn.
- Kết quả giữ nguyên thứ tự Kết luận → Mức mua tối đa → Khoảng cách giá → Lý do → Bằng chứng.

### Theo dõi và Thị trường

- Tab luôn nhìn thấy; không chuyển vào menu **More**.
- Search và filter được wrap thành nhiều hàng nếu thiếu chiều rộng; không giấu filter trong nút riêng chỉ dành cho mobile.
- Chọn một item mở detail panel bên phải trên desktop/tablet và full-screen sheet trên mobile.
- Đóng panel/sheet giữ nguyên tab, search, filter và vị trí danh sách.

## Tables và dữ liệu dày

- Không xóa cột dữ liệu trên tablet/mobile.
- Với danh sách tác vụ, mỗi table row chuyển thành record stack có label rõ cho từng giá trị.
- Với bảng cần so sánh ngang, dùng vùng cuộn ngang có chỉ dấu rằng còn nội dung phía bên phải.
- Header định danh quan trọng được giữ khi cuộn ngang nếu cần.
- Chart giữ đủ series và điểm dữ liệu; giảm mật độ tick hoặc label không đồng nghĩa bỏ dữ liệu, vì giá trị đầy đủ vẫn truy cập được bằng focus/tap.

## Touch và accessibility

- Touch target tối thiểu `44 × 44px`.
- Input trên mobile dùng cỡ chữ hiển thị tối thiểu `16px` để tránh zoom ngoài ý muốn.
- Không có hover-only interaction.
- Focus order theo thứ tự đọc sau khi layout reflow.
- Sheet, autocomplete và popover có focus management, đóng được bằng nút rõ ràng và phím Escape khi có bàn phím.
- Không khóa orientation; portrait và landscape đều dùng được.

## Overflow và stability

- Page không có horizontal overflow ngoài vùng table được chủ động cho phép cuộn.
- Nội dung không overlap, clip hoặc nhảy vị trí khi loading kết thúc.
- Primary action không bị keyboard ảo che trên mobile.
- Thay đổi viewport hoặc orientation không làm mất input, selection, search, filter hay kết quả hiện tại.

## Responsive acceptance gate

Mỗi page chỉ được coi là hoàn chỉnh khi kiểm tra đủ:

1. Desktop `1440px`.
2. Tablet portrait `768px`.
3. Tablet landscape `1024px`.
4. Mobile `390px`.
5. Mobile nhỏ `320px`.

Tại mỗi kích thước phải hoàn thành được core journey tương ứng, nhìn thấy đủ dữ liệu và
action, không có content bị ẩn theo breakpoint và không có page-level horizontal overflow.

