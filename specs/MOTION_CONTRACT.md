# Motion and Page Transition Contract

**Trạng thái:** Baseline đã chốt ngày 2026-08-25.  
**Mục tiêu:** Tạo cảm giác liên tục và hiện đại khi điều hướng mà không làm chậm quyết định.

## Nguyên tắc

- Motion giải thích thay đổi vị trí hoặc trạng thái; không dùng chỉ để trang trí.
- Page transition và data loading là hai trạng thái khác nhau.
- Không dùng global spinner để thay cho page transition.
- Không chờ dữ liệu tải xong mới bắt đầu chuyển trang.
- App shell và navigation giữ ổn định; chỉ content region chuyển động.
- Transition không được trì hoãn khả năng tương tác sau khi content đã sẵn sàng.

## Route transition

Áp dụng khi chuyển giữa **Thẩm định**, **Theo dõi** và **Thị trường**:

1. Content cũ giảm opacity và dịch tối đa `4px` trong `90–120ms`.
2. Content mới tăng opacity và trở về vị trí tự nhiên trong `140–180ms`.
3. Tổng cảm nhận không vượt quá `240ms`.
4. Không animate app shell, navigation hoặc data status.
5. Không dùng blur, zoom lớn, bounce, elastic, 3D rotate hoặc full-screen wipe.

Nếu content mới chưa sẵn sàng sau transition, page mới giữ đúng khung layout và hiển thị
loading state tại khu vực dữ liệu đang chờ. Không quay lại page cũ và không che toàn app.

## Tab transition

- Chuyển tab dùng crossfade nhẹ `100–140ms` trong content region.
- Tab indicator di chuyển cùng selection nhưng không bounce.
- Search/filter riêng của mỗi tab được giữ khi người dùng quay lại tab đó.
- Không chạy lại page transition khi chỉ đổi tab.

## Detail panel và sheet

- Desktop/tablet: detail panel trượt từ phải vào trong `180–220ms`; list phía sau không dịch chuyển đột ngột.
- Mobile: full-screen detail sheet trượt từ phải vào, giữ cảm giác đi sâu vào item; đóng sheet chạy hướng ngược lại.
- Khi đổi trực tiếp từ item này sang item khác, panel giữ vị trí và chỉ thay content bằng crossfade ngắn.
- Focus chuyển vào heading của detail khi mở và trở về item đã kích hoạt khi đóng.

## Popover và autocomplete

- Data popover và autocomplete xuất hiện bằng opacity cùng dịch chuyển tối đa `4px` trong `100–140ms`.
- Không scale từ tâm màn hình và không animate từng dòng kết quả tuần tự.
- Loading trong autocomplete nằm tại chính vùng đề xuất.

## Feedback motion

- Toast vào/ra trong `120–180ms`, không tự nảy hoặc rung.
- Validation error không làm layout giật; vùng lỗi được giữ chỗ hoặc mở theo trục dọc với motion ngắn.
- Kết quả thẩm định mới có thể dùng một lần crossfade; không animate số đếm từ 0 và không phát sáng verdict.

## Approved animation registry

Chỉ các animation sau nằm trong baseline:

| Tình huống | Animation được phép | Mục đích |
|---|---|---|
| Chuyển route | Fade và dịch chuyển nhẹ content region | Giữ continuity giữa ba khu vực |
| Chuyển tab | Crossfade content và di chuyển tab indicator | Cho biết context đã đổi nhưng vẫn ở cùng page |
| Mở detail | Panel/sheet trượt từ phải | Thể hiện đi sâu vào item đã chọn |
| Chọn sản phẩm | Trạng thái input chuyển sang Đã xác nhận bằng border/icon ngắn | Xác nhận identity đã được khóa |
| Kết quả thẩm định xuất hiện | Reveal một lần cho toàn result region | Thu hút sự chú ý vào kết quả mới |
| Dữ liệu chart thay đổi | Nội suy vị trí line/mark giữa hai state | Giúp người dùng hiểu xu hướng đã thay đổi |
| Lưu hoặc bỏ lưu | Icon và label đổi state, kèm toast ngắn | Xác nhận hành động đã hoàn thành |
| Filter hoặc status đổi | Row giữ vị trí hoặc dịch chuyển ngắn khi danh sách sắp xếp lại | Giúp theo dõi item thay vì nhìn thấy list nhảy đột ngột |

Không phải mọi tình huống đều bắt buộc animate. Nếu motion không giúp người dùng nhận biết
thay đổi hoặc vị trí, dùng state change tức thời.

## Animation budget

- Mỗi interaction chỉ có một chuyển động chính.
- Không chạy quá hai vùng motion đồng thời.
- Không stagger từng card, row, metric hoặc ký tự.
- Không chạy intro animation khi mở app hoặc mỗi lần vào page.
- Không loop animation ngoài progress indicator đang biểu thị công việc thật.
- Không thêm animation dependency khi CSS, browser hoặc transition có sẵn của framework đã đáp ứng contract.
- Animation không được tải asset video, canvas hoặc WebGL chỉ để trang trí.

## Animation không được phép

- Animated gradient, particle background, aurora, glow chạy liên tục.
- Parallax, scroll-jacking hoặc section bay vào theo scroll.
- Text typing effect, count-up từ 0 hoặc logo intro.
- Shimmer trên toàn page, skeleton chạy vô hạn khi không có request thật.
- Bounce, elastic, confetti hoặc rung element để thu hút chú ý.
- Auto-carousel, ambient 3D hoặc video nền.
- Animation riêng cho từng card/row chỉ để giao diện trông nhiều chuyển động.

## Interruptibility và state

- Người dùng có thể điều hướng tiếp khi transition đang chạy; motion cũ phải bị hủy hoặc nối tiếp an toàn.
- Double click hoặc tap liên tiếp không tạo hai navigation hay hai request.
- Scroll, input, selection, search và filter được giữ đúng theo navigation contract.
- Back/forward của trình duyệt dùng cùng transition và phục hồi đúng state.

## Reduced motion

Khi thiết bị bật `prefers-reduced-motion: reduce`:

- bỏ translate, slide và các motion theo quãng đường;
- dùng state change tức thời hoặc opacity rất ngắn;
- không mất feedback, focus management hoặc loading state.

Reduced motion là accessibility behavior bắt buộc, không phải tùy chọn theme.

## Performance gate

- Chỉ animate thuộc tính không gây layout thrashing, ưu tiên opacity và transform.
- Không để animation làm input, scroll hoặc touch bị giật.
- Không chạy transition khi initial app load.
- Không chạy animation lặp vô hạn ngoài progress indicator có mục đích rõ ràng.
- Phải kiểm tra motion trên desktop, tablet, mobile và thiết bị bật reduced motion.
