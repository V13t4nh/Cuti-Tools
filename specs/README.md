# Product Specifications

Thư mục này là nguồn sự thật cho cấu trúc sản phẩm và hành vi người dùng của CUTI.
Nội dung đã được chốt tại đây thay thế các kết luận chỉ tồn tại trong lịch sử trao đổi.

## Thứ tự nguồn sự thật

1. [IA.md](./IA.md) xác định người dùng đi đâu và các nhóm thông tin liên hệ với nhau thế nào.
2. Các tài liệu trong [features](./features/) xác định luật hành vi riêng của từng tính năng.
3. Các tài liệu trong [journeys](./journeys/) nối nhiều feature thành luồng đầu-cuối và kiểm tra cognitive bottlenecks.
4. [GLOBAL_UX_RULES.md](./GLOBAL_UX_RULES.md) áp dụng thống nhất hành vi và trạng thái trên toàn bộ frontend.
5. [RESPONSIVE_CONTRACT.md](./RESPONSIVE_CONTRACT.md) bắt buộc feature/content parity trên desktop, tablet và mobile.
6. [MOTION_CONTRACT.md](./MOTION_CONTRACT.md) quy định page transition và motion cho tab, detail, feedback.
7. [UX_CONTRACT.md](./UX_CONTRACT.md) tổng hợp những gì người dùng phải quan sát và thực hiện được trên giao diện.
8. [SCREEN_INVENTORY.md](./SCREEN_INVENTORY.md) xác định toàn bộ màn hình và state phải dựng.
9. API contract và UI implementation phải tuân theo các lớp trên.

Khi có xung đột, không sửa UI để che xung đột. Cần cập nhật tài liệu nguồn tương ứng và
chốt lại hành vi trước khi triển khai.

## Trạng thái hiện tại

- IA: baseline đã chốt ngày 2026-08-25.
- Product Search: baseline đã chốt ngày 2026-08-25.
- Saved Items: baseline đã chốt ngày 2026-08-25.
- Auction Lot Discovery: baseline YAGNI đã chốt ngày 2026-08-25.
- Liquidity Market: baseline YAGNI đã chốt ngày 2026-08-25.
- Core Journey Thẩm định: flow và cognitive bottleneck coverage đã chốt ngày 2026-08-25; usability test còn pending.
- Global UX Rules: baseline toàn dự án đã chốt ngày 2026-08-25.
- Responsive UX Contract: parity 100% trên desktop, tablet và mobile đã chốt ngày 2026-08-25.
- Motion Contract: route, tab, detail, popover và reduced-motion đã chốt ngày 2026-08-25.
- UX Contract: phiên bản 0.3, bao phủ toàn bộ IA.
- Implementation: Vue 3 + TypeScript + Vite đã nối ba route, bốn tab, detail panel/sheet và data popover với API/SQLite thật ngày 2026-08-25; không có production fixture.
