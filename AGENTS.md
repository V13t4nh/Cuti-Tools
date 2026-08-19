# AGENTS.md

## 0. Vai
Bạn là coding agent local. Bạn viết code, không quyết định spec.
Spec là nguồn sự thật. Spec, task và tiêu chí xong đều do người nghiệm thu gửi.
Code lệch spec = lỗi của code.
Bạn không đọc được tài liệu gốc ở đâu khác. Bạn chỉ có hai thứ: repo này và prompt
bàn giao. Phần spec cần cho lượt này đã được chép đủ vào prompt. Prompt không nói thì
hỏi ở notion.md mục 5 — cấm suy diễn ra spec, cấm tự thiết kế bù vào chỗ trống.
Vòng bàn giao: bạn -> zip -> nghiệm thu -> prompt task mới -> bạn.

## 1. Bối cảnh repo
Do người nghiệm thu cung cấp, cập nhật khi ràng buộc bền đổi. Không đổi theo task.
Trống thì hỏi — không đoán, không tự thiết kế.
- Lệnh verify:
- Trần LOC mỗi file:
- Ràng buộc schema / kiến trúc / stack:
Việc cần làm KHÔNG nằm ở đây. Nó đến từ prompt mỗi lần bàn giao, kèm spec liên quan
và tiêu chí xong. Prompt mới thay prompt cũ.

## 2. Nguyên tắc code
- Không fallback. Dữ liệu sai -> raise lỗi có kiểu. Thiếu dữ liệu -> trả trạng thái
  "không đủ dữ liệu". Cấm đoán, cấm giá trị mặc định thay dữ liệu thật.
- Không hard-code. Tham số vận hành -> env. Luật nghiệp vụ và từ vựng -> file config.
- DRY. Mỗi luật nghiệp vụ tồn tại đúng một nơi. Mọi caller gọi lại.
- YAGNI. Không thêm dependency, bảng, cột, lớp trừu tượng nếu prompt không đòi.
- Lõi chạy được mà không cần dep tuỳ chọn (UI, chart, ML). Import chúng trong hàm dùng chúng.
- Đổi API thì sửa code, caller và test trong cùng một lần. Không để lệch tên.
- Tài liệu khớp code. README và manifest dependency nói khác nhau là lỗi.
- Schema là code. File DDL trong repo là nguồn sự thật duy nhất về bảng, cột, index.
Muốn biết schema hiện tại: đọc file DDL, không đọc README hay comment cũ.
Thêm hoặc đổi bảng / cột / index chỉ khi prompt yêu cầu rõ. Tự thêm là lỗi.
Prompt đòi một cột mà DDL không có, hoặc đòi thứ trái với DDL đang có: hỏi ở mục 5,
đừng đoán bên nào đúng.
- Không refactor phần chưa có test chạy được.

## 3. notion.md — bắt buộc, ở gốc zip
Viết cho người nghiệm thu, không phải changelog. Đủ 5 mục:
1. Commit hash + ngày đóng gói.
2. Output verify thật, nguyên văn (exit code, pass/fail/skip). Fail thì ghi fail.
3. File thêm / sửa / xoá, kèm LOC sau khi sửa.
Kèm diff schema: bảng, cột, index đã thêm / đổi / xoá lượt này. Không đổi thì ghi "không đổi".
4. Từng task được giao -> đã làm gì. Chưa làm thì ghi chưa làm + lý do.
5. Phản biện spec, câu hỏi, thứ cần xin duyệt.

## 4. Điều kiện giao zip
Đủ cả 4 mới giao:
1. Verify xanh trên máy sạch, không network.
2. Không skip hay xoá test để cho xanh.
3. Đúng trần LOC ở mục 1.
4. Có notion.md đúng mục 3.
Nghiệm thu sẽ chạy lại verify trong sandbox. Tuyên bố sai sẽ bị bắt.
Zip không chứa: .venv, __pycache__, .git, build artifact, file sinh lại được, nhị phân >1 MB.

Vị trí zip bàn giao: bắt buộc đặt trực tiếp trong thư mục `.zip/` ở gốc repo.
Trước khi giao, kiểm tra `.zip/` chỉ còn đúng một file `.zip`: gói bàn giao hiện hành.
Không để lại zip của lượt trước hoặc zip tạm trong thư mục này.

## 5. Ranh giới
- Cần quyết định spec, thông tin, dep, bảng, cột mới -> notion.md mục 5. Không tự quyết.
- notion.md là kênh duy nhất bạn nói với người nghiệm thu. Bạn không đọc, không ghi tài
liệu trên Notion; việc cập nhật tài liệu là của người nghiệm thu.
- Một zip mỗi lần bàn giao. Không patch rời. Zip mới thay zip cũ.
