# Core Journey: Thẩm định cơ hội mua

**Trạng thái:** UX flow và cognitive bottleneck coverage đã chốt ngày 2026-08-25.  
**Phạm vi xác nhận:** Contract-level. Chưa qua usability test trên prototype.

## User Flow

```mermaid
flowchart TD
    A([Trigger: Người dùng gặp một cơ hội mua]) --> B[Nhập tên, model hoặc reference]

    B --> C[[System Check: Tìm tối đa 10 sản phẩm gần nhất]]
    C --> D{Search hoạt động?}

    D -- Không --> E[Thông báo lỗi tìm kiếm]
    E -->|Thử lại| B
    E -->|Dừng| E1([End: Chưa thể thẩm định])

    D -- Có --> F{Có sản phẩm phù hợp?}
    F -- Không --> G[Thông báo: Không tìm thấy sản phẩm phù hợp]
    G -->|Sửa từ khóa| B
    G -->|Dừng| G1([End: Không xác định được sản phẩm])

    F -- Có --> H[Hiển thị tối đa 10 đề xuất]
    H --> I[Người dùng chọn một sản phẩm]
    I --> J{Sản phẩm chuẩn đã được xác nhận?}

    J -- Không --> B
    J -- Có --> K[[System Check: Kiểm tra trạng thái dữ liệu]]

    K --> L{Độ mới dữ liệu?}
    L -- No data --> M[Chặn thẩm định và thông báo chưa có dữ liệu thị trường]
    M --> M1([End: Không thể thẩm định; có thể Lưu mẫu])

    L -- Stale --> N[Cảnh báo dữ liệu đã cũ và hiển thị thời điểm cập nhật]
    L -- Fresh --> O[Cho phép tiếp tục]
    N --> O

    O --> P[Người dùng nhập giá người bán chào, tiền tệ và tình trạng]
    P --> Q[[System Check: Kiểm tra dữ liệu nhập]]
    Q --> R{Thông tin hợp lệ và đầy đủ?}

    R -- Không --> S[Chỉ rõ trường sai hoặc còn thiếu]
    S --> P

    R -- Có --> T[[System Check: Tìm dữ liệu so sánh, tính mức mua và rủi ro]]
    T --> U{Đủ bằng chứng để kết luận?}

    U -- Không --> V[Hiển thị Không đủ dữ liệu; không hiển thị số suy diễn]
    V --> V1([End: Chưa có kết luận; có thể Lưu mẫu])

    U -- Có --> W[Hiển thị kết luận, mức mua tối đa, lý do và bằng chứng]
    W --> X{Người dùng chủ động muốn lưu gì?}

    X -- Không lưu --> Y([End: Kết quả tạm thời; không tạo lịch sử])
    X -- Chỉ Lưu mẫu --> Z([End: Mẫu đã lưu; kết quả không được lưu])
    X -- Lưu thương vụ --> AA[[Lưu bối cảnh thẩm định]]
    X -- Lưu cả hai --> AB[[Lưu mẫu và bối cảnh thẩm định]]
    AB --> AA

    AA --> AC[Trạng thái: Đang cân nhắc]
    AC --> AD{Quyết định sau đó}
    AD -- Tiếp tục cân nhắc --> AC
    AD -- Chốt giao dịch --> AE([End: Đã mua])
    AD -- Không tiếp tục --> AF([End: Đã bỏ qua])
```

## Cognitive Bottleneck Coverage

| Bottleneck | Behavior bắt buộc | Trạng thái coverage |
|---|---|---|
| Chọn nhầm sản phẩm | Tên chuẩn và reference; exact reference đứng đầu; không tự chọn; sửa tên hủy xác nhận và kết quả cũ | Covered by contract |
| Nhầm giữa đã nhập và đã chọn | Hiện trạng thái Đã xác nhận; chưa chọn đề xuất thì không được thẩm định | Covered by contract |
| Không biết dữ liệu còn đáng tin không | Fresh không gây nhiễu; Stale cảnh báo nhưng cho tiếp tục; No data chặn và giải thích | Covered by contract |
| Nhập sai giá hoặc tiền tệ | Giá và tiền tệ đi cùng nhau; không tự chọn tiền tệ; định dạng rõ; lỗi đặt tại trường và giữ nguyên input | Covered by contract |
| Quá tải khi đọc kết quả | Thứ tự Kết luận → Mức mua tối đa → Khoảng cách giá → Lý do → Bằng chứng; không chỉ dùng màu | Covered by contract |
| Nhầm Lưu mẫu với Lưu thương vụ | Hai hành động đặt ở hai ngữ cảnh khác nhau và phản hồi nói rõ thứ vừa được lưu | Covered by contract |
| Tưởng rằng kết quả đã tự lưu | Hiện Chưa lưu; rời luồng không tạo lịch sử; không dùng modal cản trở | Covered by contract |
| Không tìm thấy sản phẩm | Giữ truy vấn, cho sửa và tìm lại, không đoán hoặc tự tạo sản phẩm | Safely handled; intentional YAGNI gap |

## Quy tắc trình bày tối thiểu

- **Lưu mẫu** nằm gần định danh sản phẩm.
- **Lưu thương vụ** nằm tại kết quả thẩm định.
- Sau khi lưu mẫu, phản hồi phải nói rõ kết quả thẩm định chưa được lưu.
- Kết quả chưa lưu phải được nhận biết mà không cần mở thêm hộp thoại.
- Không dùng popup cho cảnh báo dữ liệu cũ hoặc khi người dùng rời kết quả chưa lưu.
- Không thêm ảnh sản phẩm, wizard, onboarding hoặc hệ trợ giúp phức tạp để giải quyết các bottleneck này trong phiên bản đầu.

## Phần còn phải kiểm chứng

Coverage phía trên xác nhận rằng mỗi rủi ro đã có behavior xử lý, không xác nhận rằng cách
trình bày đã dễ hiểu trong thực tế. Sau khi có wireframe hoặc prototype, cần kiểm tra tối thiểu:

- người dùng có nhận ra họ phải chọn một đề xuất hay không;
- người dùng có phân biệt đúng Lưu mẫu và Lưu thương vụ hay không;
- người dùng có hiểu Stale vẫn dùng được còn No data thì không hay không;
- người dùng có tìm được kết luận và mức mua tối đa mà không đọc toàn bộ bằng chứng hay không.

