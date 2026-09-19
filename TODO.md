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

---

## 3. Kế hoạch Phát triển Tương lai (Backlog)

### 3.1. Vấn đề 3: Từ điển Viết tắt & Tiếng lóng Đồng hồ (Watch Acronyms & Slang)
- **Bối cảnh**: Người sưu tầm và giao dịch đồng hồ thường xuyên sử dụng các từ viết tắt hoặc biệt danh:
  - `DJ` $\rightarrow$ Datejust, `DD` $\rightarrow$ Day-Date
  - `KS` $\rightarrow$ King Seiko, `GS` $\rightarrow$ Grand Seiko
  - `Sub` $\rightarrow$ Submariner, `Speedy` $\rightarrow$ Speedmaster
  - `SMP` $\rightarrow$ Seamaster Professional, `PO` $\rightarrow$ Planet Ocean
  - `BB58` / `BB` $\rightarrow$ Black Bay 58 / Black Bay
- **Kế hoạch**:
  - [ ] Thiết kế bảng `watch_synonyms` / Từ điển Thesaurus ánh xạ từ viết tắt sang tên đầy đủ.
  - [ ] Tích hợp tầng Query Expansion trong `search_query.py` để tự động mở rộng từ khóa viết tắt thành biểu thức OR khi truy vấn cơ sở dữ liệu.

### 3.2. Vấn đề 4: Tách biệt UX giữa Liquidity (Thương hiệu) & Auctions (Tìm kiếm tự do)
- **Bối cảnh**:
  - Tab **Liquidity** (`/market?tab=liquidity`) tổng hợp chỉ số thanh khoản, khối lượng và biểu đồ giá theo cấp **Brand** (Rolex, Omega, Seiko...). Nếu người dùng tìm kiếm chuỗi tự do (như `Datejust 36`, `Omega 42mm`), Liquidity sẽ báo "không đủ dữ liệu" do chưa hỗ trợ aggregate theo model tùy ý.
  - Tab **Auctions** (`/market?tab=auctions`) là nơi tìm kiếm toàn diện mọi lot, dòng máy, kích thước vỏ, số la mã... từ sàn đấu giá.
- **Kế hoạch**:
  - [ ] Phân định rõ phạm vi tìm kiếm của Header Search / Autocomplete: khi ở tab Liquidity chỉ gợi ý các Brand hoặc Canonical Model đã định hình.
  - [ ] Thêm thông báo hướng dẫn hoặc tự động chuyển hướng sang tab Auctions khi người dùng chọn một sản phẩm/model thị trường tự do (`market:<slug>`).

### 3.3. Vấn đề 5: Cơ chế Hiệu chỉnh Định giá cho Model Thị trường Tự do (Dynamic Calibration for Market Models)
- **Bối cảnh**:
  - Tính năng Thẩm định (`/pricing`) sử dụng các bộ tham số hiệu chỉnh (Calibration Parameters: `delta_pct`, `haircut_pct`, `cost_vnd`) được cấu hình trong `rules.json` cho từng Canonical Product.
  - Khi người dùng khám phá và lưu một model mới từ thị trường (`market:<slug>`), hệ thống chưa có tham số hiệu chỉnh riêng, dẫn đến thiếu công thức tính giá trần/giá sàn chính xác.
- **Kế hoạch**:
  - [ ] Xây dựng cơ chế kế thừa tham số định giá (Inheritance Rules): model mới kế thừa `haircut` và biên lợi nhuận mặc định theo Brand hoặc Price Tier tương ứng.
  - [ ] Cho phép người dùng tùy chỉnh và lưu tham số Calibration riêng cho từng sản phẩm thị trường trực tiếp trên UI.

