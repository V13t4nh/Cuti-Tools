# Thư mục thử nghiệm cào dữ liệu qua Giả lập TLS (curl-cffi)

Thư mục này là một môi trường độc lập (sandbox/playground) để thử nghiệm cơ chế cào dữ liệu từ Catawiki bằng kỹ thuật **TLS Fingerprint Impersonation** (giả lập chữ ký TLS của trình duyệt Chrome 124) thay vì phải mở trình duyệt thật.

---

## 1. Cấu trúc thư mục

- `crawler.py`: Module crawler độc lập `CatawikiTlsCrawler`, tích hợp `curl-cffi`, quản lý phiên làm việc, tự động giãn cách độ trễ an toàn (`pause_seconds`), tìm kiếm, lấy live status và bóc tách thông số HTML trang lot.
- `run_test.py`: Script chạy mẫu tương tác qua dòng lệnh.
- `output/`: Chứa file kết quả JSON xuất ra sau mỗi lần chạy (`crawled_sample.json`).

---

## 2. Cách chạy thử nghiệm

Bạn có thể chạy thử nghiệm trực tiếp từ PowerShell tại thư mục gốc dự án:

```powershell
# Chạy mặc định (tìm "Omega Speedmaster", lấy 3 lot)
.\.venv\Scripts\python.exe playground\tls_crawler\run_test.py

# Tìm kiếm theo thương hiệu / từ khóa tùy ý
.\.venv\Scripts\python.exe playground\tls_crawler\run_test.py --query "Rolex Submariner" --limit 5

# Điều chỉnh độ trễ an toàn giữa các request (ví dụ 1.2 giây)
.\.venv\Scripts\python.exe playground\tls_crawler\run_test.py --query "Seiko" --limit 4 --pause 1.2
```

---

## 3. Ưu điểm quan sát được

1. **Tốc độ**: Mỗi request chỉ tốn từ 400ms – 1s, toàn bộ luồng tìm kiếm + lấy trạng thái + bóc tách HTML nhiều lot xong trong vài giây.
2. **Không tốn tài nguyên**: Chạy ngầm hoàn toàn qua HTTP/TLS, không mở bất kỳ cửa sổ trình duyệt nào, tiêu thụ RAM không đáng kể.
3. **Vượt WAF mượt mà**: Chữ ký TLS Chrome 124 giúp tránh được lỗi `HTTP 403 Access Denied` của WAF Catawiki.
4. **An toàn cho IP**: Cơ chế `_wait_pacing()` tự động giữ khoảng nghỉ giữa các request để không kích hoạt Rate Limit của sàn.
