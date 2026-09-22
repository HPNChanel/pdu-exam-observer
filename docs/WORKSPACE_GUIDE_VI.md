# PDU Exam Observer — vận hành workspace cục bộ

Bản này nối luồng bài thi, ghi tư thế, duyệt video, export và nhập model. Nhãn
chỉ mô tả chuyển động quan sát được. Người đánh giá phải đối chiếu bằng chứng;
ứng dụng không kết luận ý định, danh tính, dùng điện thoại hoặc gian lận.

## Khởi động

Giải nén toàn bộ ZIP ứng dụng vào thư mục có quyền ghi. Chạy `START.cmd`, nhập
PIN riêng cho lần chạy. Giữ cửa sổ launcher trong suốt phiên; dừng bằng Ctrl+C.
PIN không được ghi vào hồ sơ phiên. Hai trang mở trên loopback:

- Bài thi: `http://127.0.0.1:8765/exam`.
- Reviewer: `http://localhost:8766/monitor?workspace=1`.

Nếu chạy từ source, dùng môi trường đã cài theo `uv.lock`:

```powershell
uv sync --extra training
uv run python -m pdu_exam_observer workspace
```

Thư mục dữ liệu mặc định nằm dưới `%LOCALAPPDATA%\PDUExamObserver\workspace`.
Công cụ native nhận `workspace --root D:\PDU-Local` để chọn một thư mục cục bộ
khác. Không dùng ổ mạng, thư mục đồng bộ đám mây hoặc junction. Trình duyệt
không nhận đường dẫn lưu trữ, URL tùy ý hay lệnh hệ thống.

## Thử toàn bộ quy trình bằng mô phỏng

1. Đăng nhập reviewer bằng PIN của launcher. Chọn **Mô phỏng kỹ thuật**, tạo phiên.
2. Nhập mã ghép cặp ở trang bài thi. Xác nhận thông tin và kiểm tra trước phiên
   trên trang bài thi; thực hiện kiểm tra trước phiên ở reviewer.
3. Bấm **Bắt đầu**. Clip skeleton sáu giây và timeline 33 landmarks được tạo
   cục bộ; nguồn luôn là `AI_RENDERED`. Đây không phải hình ảnh từ camera.
4. Thử trả lời bài thi. Trạng thái lưu bài nằm ở trang bài thi. Reviewer có
   skeleton trực tiếp, chất lượng và trạng thái phiên; bài thi không nhận nhãn
   nghiên cứu, confidence hay điều khiển reviewer.
5. Bấm **Dừng**, rồi **Niêm phong**. Chỉ sau seal mới xem được video cục bộ.
6. Duyệt từng sự kiện: sửa biên thời gian tính bằng mili giây, chọn nhãn và
   xác nhận/từ chối/chưa đủ bằng chứng, ghi lý do. Mỗi lần sửa thêm một phiên
   bản. **Gán nhãn đoạn video khác** cho phép ghi nhận đoạn bỏ sót hoặc đoạn
   bình thường. Các khoảng có nhãn mâu thuẫn phải được xử lý trước khi khóa.
7. **Khóa dữ liệu đã duyệt**, rồi **Xuất dữ liệu pose**. ZIP chỉ có manifest
   và JSONL theo envelope cho phép; không có video, danh tính, đường dẫn hoặc
   audit người vận hành. Các đoạn chưa được xác nhận xuất nhãn `UNCERTAIN`.
8. **Lưu báo cáo duyệt cục bộ** lưu bản tổng hợp và lịch sử duyệt để sử dụng
   trên máy. Báo cáo này có ghi chú người duyệt, không phải gói đưa lên Colab.
9. Mục dọn dữ liệu thử xóa artifact mô phỏng của phiên và giữ biên bản. Đây là
   thao tác xóa có chủ đích; dùng bản mô phỏng để tập quy trình trước.

## Camera và phiên nghiên cứu thật

Chế độ REAL cần đủ màn hình vật lý, camera đúng profile, lưu trữ hợp lệ và hồ sơ
native gắn đúng participant/session/root. Hai cửa sổ trên một màn hình không
đáp ứng điều kiện hai màn hình. Camera dùng device 0, 1280×720, yêu cầu 15 FPS,
không mở audio. Một tiến trình riêng sở hữu camera; khởi tạo/đọc/đóng có timeout.

Trước khi thu bất kỳ người tham gia nào, người có thẩm quyền phải cung cấp
phê duyệt tổ chức, consent, retention và bằng chứng storage. Không sửa JSON để
tự biến trạng thái chưa phê duyệt thành đã phê duyệt. Công cụ cài đặt xác minh
băm tài liệu và ràng buộc bản ghi; nó không chứng minh tính xác thực học thuật
của tài liệu do người vận hành cung cấp.

Tạo phiên REAL trước để lấy `session_id`. Bản ghi native nằm trong thư mục
`research` của workspace. Mẫu và danh sách trường được cung cấp bởi
`research_runtime/authority_cli.py` (`template_main`; hiện chỉ gọi được từ mã
nguồn — chưa nối vào `PDUWorkspace.exe`); mẫu chỉ chứa placeholder. Công cụ
đóng gói có lệnh `PDUWorkspace.exe authority --help`. Cài hồ sơ bằng các đối số
`--root`, `--record`, `--approval-file`, `--consent-file`, `--retention-file`,
`--storage-evidence-file`; tất cả chỉ được nhập ở terminal native. Khi thay hồ
sơ cũ, bắt buộc `--expected-current-sha256`. Cấu hình
`PDU_COLLECTION_AUTHORITY_REF` trong môi trường launcher khớp hồ sơ được cài.

Nguồn REAL chỉ được export khi consent còn hiệu lực, retention chưa hết hạn,
phiên đã seal và khóa. `timing.phase` được lấy từ cohort PILOT/CONFIRMATORY
trong hồ sơ native, không lấy từ trình duyệt. Phiên PILOT không được dùng làm
kết quả confirmatory.

Luật minh họa không phải ngưỡng nghiên cứu đã được phê chuẩn. File native
`research\.pdu_exam_observer\frozen-rules.v1.json` chứa cùng protocol freeze
đã dùng cho bộ huấn luyện: self-hash hợp lệ, `status=FROZEN`,
`policy_selection_source=PILOT` hoặc `CALIBRATION`, phiên bản khớp hồ sơ native.
Các ngưỡng, thời gian duy trì, release, gộp và cooldown phải được ghi rõ.
Góc trong baseline là đại lượng hình học trên ảnh, không phải đo pitch/yaw
giải phẫu. Thiếu chính sách thì suy luận luật được báo thiếu bằng chứng;
hệ thống không tự chọn ngưỡng bằng tập test. Model smoke chỉ dùng với mô phỏng.

## Nhập model và Colab

Gói Colab được bàn giao riêng, gồm notebook tự chứa code, cấu hình/dependency
đã khóa, dữ liệu smoke và hướng dẫn. Chạy **smoke** trước. Chế độ nghiên cứu
phải qua kiểm tra phê duyệt, provenance, cohort và chia participant; không đổi
`source_kind` của dữ liệu mô phỏng thành REAL.

Notebook tạo model bundle riêng với báo cáo. Tại reviewer, chọn **Nhập gói
model ZIP**. Hệ thống kiểm tra danh sách file, checksums, tensor/schema,
preprocessing và golden inference trước khi kích hoạt. Nếu thất bại, model
đang dùng được giữ lại. Confidence/abstention không phải kết luận kỷ luật.

## Gián đoạn, cách ly và rút dữ liệu

Không tự đổi trạng thái FAILED thành SEALED. Sau gián đoạn, mở lại cùng root:
phiên chưa dừng được đánh FAILED, file dở được giữ ở trạng thái quarantine để
đối soát. Giữ nguyên hồ sơ và tạo phiên mới sau khi khắc phục lỗi. Không nối
file dở vào một phiên mới. Sai schema, hash hoặc đường dẫn khiến thao tác dừng
lại; không xóa manifest để bỏ qua lỗi.

Khi một người rút consent, cài bản thay thế native với trạng thái
REVOKED/WITHDRAWN, quyết định DELETE_OWNED_RUNTIME_ARTIFACTS hoặc
QUARANTINE_RUNTIME_ARTIFACTS và băm hồ sơ xóa (`--deletion-file`). Mục rút dữ
liệu ở reviewer thực hiện đúng quyết định đã cài, chỉ trên artifact thuộc
phiên. Việc này chặn thu thập/export tiếp. Export đã tải ra ngoài phải được
đối soát riêng; ứng dụng không thể thu hồi bản sao nằm ngoài root.

## Phạm vi bằng chứng

Kiểm thử giả lập chứng minh đường đi kỹ thuật của code, không chứng minh độ
chính xác nghiên cứu hay hành vi camera trên mọi máy. Lần kiểm tra hiện tại
chỉ dùng máy đang có. Kiểm thử máy mới được hoãn theo yêu cầu và vẫn UNVERIFIED.
Phê duyệt tổ chức, pilot/confirmatory và huấn luyện nghiên cứu thật chưa được
thực hiện trong đợt bàn giao này. Bản ZIP là ứng viên kỹ thuật cục bộ; không có
ủy quyền phát hành, triển khai hay thu người tham gia.
