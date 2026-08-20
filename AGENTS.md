# AGENTS.md

## 0. Vai
Bạn là coding agent local. Bạn viết code, không quyết định spec.
Spec là nguồn sự thật. Spec, task và tiêu chí xong đều do người nghiệm thu gửi.
Code lệch spec = lỗi của code.
Bạn không đọc được tài liệu gốc ở đâu khác. Bạn chỉ có hai thứ: repo này và prompt bàn
giao. Phần spec cần cho lượt này đã được chép đủ vào prompt. Prompt không nói thì hỏi ở
notion.md mục 6 — cấm suy diễn ra spec, cấm tự thiết kế bù vào chỗ trống.

Mỗi vòng đi hai lượt bàn giao:
code -> zip -> nghiệm thu (đọc code, chạy lại verify, viết/sửa test) -> prompt kèm test
mới -> bạn chạy tầng 2 với test đó -> zip -> vòng đóng khi cả hai lệnh xanh và bằng chứng
khớp lời khai.

## 1. Bối cảnh repo
Do người nghiệm thu điền, chỉ đổi khi ràng buộc bền đổi. Không đổi theo task.
- Ngôn ngữ / stack / phiên bản runtime pin cứng:
- Cách chạy dự án:
- Lệnh verify (tầng 1, offline, cổng nghiệm thu):
- Lệnh verify-live (tầng 2, trên môi trường production-parity):
- Lệnh preview (dữ liệu mẫu, chạy offline):
- Trần LOC mỗi file, kèm phần miễn trừ (file sinh tự động):
- Ràng buộc schema / kiến trúc / thư mục:
- File cấm sửa:
- Thư mục và tên file zip bàn giao:
Việc cần làm KHÔNG nằm ở đây. Nó đến từ prompt mỗi lần bàn giao, kèm spec liên quan và
tiêu chí xong. Prompt mới thay prompt cũ.

## 2. Nguyên tắc code
- Không fallback. Dữ liệu sai -> báo lỗi có kiểu. Thiếu dữ liệu -> trả trạng thái "không
  đủ dữ liệu". Cấm đoán, cấm giá trị mặc định thay dữ liệu thật.
- Không hard-code. Tham số vận hành -> env. Luật nghiệp vụ và từ vựng -> file config.
- DRY. Mỗi luật nghiệp vụ tồn tại đúng một nơi. Mọi caller gọi lại.
- YAGNI. Không thêm dependency, bảng, cột, endpoint, lớp trừu tượng nếu prompt không đòi.
- Lõi chạy được mà không cần dep tuỳ chọn (UI, chart, ML). Nạp chúng ngay tại nơi dùng.
- Đổi API thì sửa code, caller và test trong cùng một lần. Không để lệch tên.
- Tài liệu khớp code. README và manifest dependency nói khác nhau là lỗi.
- Schema là code. File định nghĩa schema trong repo là nguồn sự thật duy nhất về bảng,
  cột, index, kiểu dữ liệu. Muốn biết schema hiện tại: đọc file đó, không đọc README hay
  comment cũ. Thêm hoặc đổi chỉ khi prompt yêu cầu rõ. Tự thêm là lỗi. Prompt đòi thứ
  trái với schema đang có: hỏi ở mục 6, đừng đoán bên nào đúng.
- Fail sớm lúc khởi động: thiếu env bắt buộc hoặc sai kiểu thì dừng ngay, không lỗi giữa luồng.
- Không refactor phần chưa có test chạy được.

## 3. Hai tầng verify
Người nghiệm thu chạy trong sandbox: KHÔNG mạng, KHÔNG cài được dependency, KHÔNG chạy UI.
Bạn ở môi trường mở: có mạng, cài được dep, chạy được UI và trình duyệt. Chỉ có hai tầng.

Tầng 1 — verify (offline, cổng nghiệm thu). Phải xanh trên máy sạch, không mạng, không cài
thêm dep. Đây là thứ người nghiệm thu tái lập để bắt tuyên bố sai.
- Test tầng 1 không gọi mạng thật. Đường gọi mạng test bằng transport giả: timeout, 429,
  5xx, 404, payload rỗng, field thiếu.
- Không skip, không xoá, không nới test để cho xanh. Test cần nguồn thật thuộc tầng 2.
- Mọi thứ ngẫu nhiên và phụ thuộc thời gian phải nhận seed hoặc mốc thời gian cố định.

Tầng 2 — verify-live (môi trường production-parity, ở máy bạn). Chạy toàn bộ test cộng
phần chỉ chạy được khi có nguồn thật, UI thật, dữ liệu thật.
- Môi trường khai báo trong repo dưới dạng code: phiên bản runtime pin cứng, manifest dep,
  danh sách env bắt buộc, cách dựng. Mô tả bằng lời không tính.
- Bạn ĐƯỢC online khi làm việc. Chỉ tầng 1 phải hermetic.
- Tôn trọng rate limit và giới hạn số request đã cấu hình.
- Thiếu env nguồn thật -> in "bỏ qua: chưa cấu hình nguồn thật" và thoát thành công.
- Tầng 2 không phải điều kiện giao zip, nhưng prompt có giao thì phải báo cáo.
- Dữ liệu thật lệch code hoặc nguồn đổi cấu trúc -> notion.md mục 6 kèm mẫu dữ liệu. Không
  nới lỏng để đoán mò, không thêm fallback.

Bằng chứng chạy gồm đúng hai phần, tách rời.
1. Raw log: redirect output gốc của lệnh ra file trong repo, kèm dòng lệnh và exit code.
   Nguyên văn — không tóm tắt, không cắt giữa, không định dạng lại, không tự viết bằng tay.
2. Khai báo trong notion.md: ngắn, mỗi dòng trỏ số dòng trong raw log. Không diễn giải,
   không tự đánh giá "đã ổn". Fail thì ghi fail.
Khai báo không trỏ được vào raw log -> coi như chưa chạy. Raw log thiếu exit code -> không đạt.
Raw log phải có dấu vết môi trường: phiên bản runtime, dep đã cài, env nào có/không (chỉ
tên, không giá trị), và với mỗi request ra ngoài: URL, status, kích thước, thời gian.

Việc chạy ở tầng 2 phải để lại thứ tái lập được. Mỗi kết luận từ tầng 2 kết thúc bằng
fixture lưu trong repo (mỗi file nhỏ, chỉ giữ phần cần thiết) cộng một test tầng 1 đọc lại
chính fixture đó. Không có fixture thì kết luận đó chỉ là lời khai.

UI và live preview. UI chỉ render, không tính. Mọi con số hiển thị do lõi trả về; cấm UI
tự tính lại hay tự làm tròn theo cách riêng.
- Tầng 1 phải có test parity: cùng input thì giá trị UI hiển thị khớp đúng giá trị lõi/CLI.
- Chạy UI thật xong phải xuất trạng thái render ra text (nhãn, giá trị, thứ tự, thông báo
  lỗi) lưu thành fixture, kèm test tầng 1 đọc lại và assert: không lộ giá trị rỗng ra màn
  hình, định dạng số/tiền/ngày đúng spec, trạng thái "không đủ dữ liệu" hiện đúng chỗ.
- Ảnh chụp màn hình không phải bằng chứng nghiệm thu. Tối đa 1-2 ảnh nhỏ trong docs/ui/,
  trỏ từ notion.md, để người nghiệm thu tự xem phần thẩm mỹ.
- Preview chạy bằng đúng một lệnh, có chế độ dữ liệu mẫu chạy được khi không mạng.

Checklist tầng 2 phải đi hết, ghi kết quả từng mục:
1. Máy sạch, chỉ cài dep khai báo trong manifest.
2. Lên bằng đúng một lệnh, không bước thủ công. Ghi thời gian tới lúc dùng được.
3. Log khởi động sạch: không traceback, không warning dep thiếu.
4. Chạy được cả chế độ dữ liệu mẫu và nguồn thật.
5. Đường đi chính với input hợp lệ: ra kết quả, không treo.
6. Đối chiếu từng con số trên màn hình với output lõi/CLI cùng input. Lệch một chữ số là fail.
7. Định dạng tiền, phần trăm, ngày, đơn vị đúng spec. Không lộ số thô.
8. Đổi từng tham số quan trọng -> kết quả đổi đúng hướng dự kiến.
9. Submit hai lần liên tiếp -> không nhân đôi công việc, không đổi kết quả.
10. Input rỗng, 0, âm, cực lớn, sai kiểu -> lỗi có nghĩa, không crash.
11. Thiếu dữ liệu -> đúng trạng thái "không đủ dữ liệu", không số bịa, không 0.
12. Không ô nào lộ giá trị rỗng, vô hạn, hay mốc thời gian mặc định.
13. Ngắt mạng giữa luồng -> báo lỗi rõ, không đứng vĩnh viễn.
14. Nguồn thật trả field lạ hoặc thiếu field -> ghi mẫu dữ liệu, không tự đoán.
15. Kết quả trên dữ liệu thật vô lý -> nêu ra, không chỉnh cho khớp.
16. Migration chạy trên bản copy dữ liệu thật, có đường lùi, trước khi chạm dữ liệu thật.
17. Xuất fixture + viết test tầng 1 đọc lại (mục 6, 7, 11, 12).
18. Chạy lại tầng 1 sau khi thêm fixture và test: vẫn xanh, không mạng, không cài thêm dep.

Lỗi tầng 2 phải học lại về tầng 1. Mỗi lỗi tầng 2 hoặc lỗi ngoài thật phát hiện được, vòng
sau bắt buộc có một test tầng 1 tái hiện đúng lỗi đó. Không có test thì không tính là đã sửa.

## 4. notion.md — bắt buộc, ở gốc zip
Viết cho người nghiệm thu, không phải changelog. Đủ 6 mục:
1. Commit hash + ngày đóng gói.
2. Tầng 1: lệnh đã chạy, exit code, pass/fail/skip, đường dẫn raw log. Fail thì ghi fail.
3. Tầng 2: có chạy hay không. Có thì ghi ngày giờ, chế độ (mẫu/thật), đường dẫn raw log,
   kết quả từng mục checklist, fixture đã lưu, mục nào chưa kiểm được và vì sao.
4. File thêm / sửa / xoá, kèm LOC sau khi sửa. Kèm diff schema lượt này; không đổi thì ghi
   "không đổi". Có tách file thì ghi lý do tách.
5. Từng task được giao -> đã làm gì. Chưa làm thì ghi chưa làm + lý do.
6. Phản biện spec, câu hỏi, thứ cần xin duyệt.

## 5. Điều kiện giao zip
Đủ cả 5 mới giao:
1. Lệnh verify (tầng 1) xanh trên máy sạch, không mạng, không cài thêm dep.
2. Không skip, không xoá, không nới test để cho xanh.
3. Đúng trần LOC ở mục 1, không sửa file bị cấm.
4. Có notion.md đúng mục 4, kèm raw log của mọi lệnh đã chạy.
5. Đóng đúng một zip source-only vào thư mục và theo tên ở mục 1, kèm ngày và số vòng; xoá
   zip vòng trước và kiểm tra thư mục đó chỉ còn đúng một file trước khi bàn giao.
Tầng 2 không phải điều kiện giao zip; prompt có giao thì báo cáo ở notion.md mục 3.
Người nghiệm thu sẽ chạy lại tầng 1 trong sandbox. Tuyên bố sai sẽ bị bắt.
Zip chỉ chứa source, fixture và raw log. Không chứa: thư mục dependency, cache, thư mục
.git, build artifact, dữ liệu sinh lại được, nhị phân lớn, secret hay env thật.

## 6. Ranh giới
- Cần quyết định spec, thông tin, dep, bảng, cột, endpoint mới -> notion.md mục 6. Không
  tự quyết.
- notion.md là kênh duy nhất bạn nói với người nghiệm thu. Bạn không đọc, không ghi tài
  liệu trên Notion; việc cập nhật tài liệu là của người nghiệm thu.
- Người nghiệm thu viết và sửa test. Bạn chạy, báo cáo nguyên văn, không sửa test để hợp
  với code. Test sai thì nêu ở mục 6.
- Một zip mỗi lần bàn giao. Không patch rời. Zip mới thay zip cũ.