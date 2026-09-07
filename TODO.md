# CUTI-TOOLS: Kế hoạch Nâng cấp & Danh sách TODO

## 1. Vấn đề cốt lõi: Hạn chế của Regex Heuristics khi bóc tách văn bản tự do

### Mô tả vấn đề
Hiện tại, hệ thống sử dụng các biểu thức chính quy (Regex) và logic cắt chuỗi tĩnh (`normalize.py`, `settlement_resolver.py`, `catawiki_lot_page.py`) để cố gắng bóc tách các trường thuộc tính từ bài viết tự do (Description) và bảng thông số (Details) của Catawiki.

### Danh sách các cột có nguy cơ bị sai do Regex:
1. **`ref_number` (Rủi ro rất cao)**:
   - Dễ bắt nhầm số serial đáy vỏ hoặc mã số phụ.
   - Bị xóa trắng (`None`) khi bài viết nhắc tới 2 mã số trở lên (`len(refs) > 1`).
2. **`caliber` (Rủi ro rất cao)**:
   - Dễ bắt nhầm máy phủ định ("không phải máy ETA 2824 mà là...").
   - Bắt nhầm các chuỗi số kỹ thuật trùng định dạng máy.
3. **`condition_tag` (Rủi ro rất cao)**:
   - Dễ gắn nhãn "Full set" ảo khi người bán ghi tiêu đề Full set nhưng trong bài lại chú thích "hộp ngoài, giấy của shop".
4. **`case_code` (Rủi ro cao)**:
   - Phụ thuộc vào `ref_number`, sai dây chuyền nếu ref bị nhận diện sai.
5. **`model` & `model_key` (Rủi ro cao)**:
   - Không nhận diện được các biến thể tên gọi không có trong từ điển cứng `rules.json`, dẫn đến phân loại vào Model chung chung hoặc Tier thấp.
6. **`case_material` (Rủi ro trung bình)**:
   - Dễ nhầm vàng đúc với mạ vàng (`gold plated`) hoặc vỏ đơ-mi (two-tone).
7. **`case_diameter_mm` (Rủi ro trung bình)**:
   - Dễ bắt nhầm độ dày (`thickness`) hoặc chiều dài càng (`lug-to-lug`) thành đường kính mặt.

---

## 2. Kế hoạch khắc phục (TODO)

- [ ] **Tích hợp tầng Preprocessor bằng LLM/SLM**:
  - Tận dụng kho dữ liệu văn bản gốc đã được lưu nén trong bảng `lot_desc` (`desc_z`).
  - Thiết kế prompt chuyên biệt đọc `desc_z` và trả về JSON chuẩn xác: Ref thật, Caliber thật, Tình trạng linh kiện zin/thay thế, Chi tiết khuyết tật.
  - Lưu kết quả vào cột `ai_json` đã thiết kế sẵn trong bảng `lots`.
- [ ] **Cơ chế Cross-Check & Cảnh báo mâu thuẫn**:
  - Đối chiếu chéo giữa `details` (thông số sàn) và `ai_json` (mô tả thật).
  - Tự động gắn cờ cảnh báo người thẩm định khi có mâu thuẫn (Ví dụ: Bảng ghi Like New nhưng bài viết ghi đã đánh bóng/xước dăm).
- [ ] **Hiển thị Description trên UI**:
  - Đưa nguyên văn bài viết mô tả (giải nén từ `lot_desc`) lên Drawer chi tiết trên màn hình `/market?tab=auctions` để người dùng tiện đối chiếu trực tiếp.
