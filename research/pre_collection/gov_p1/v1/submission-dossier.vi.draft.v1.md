# Hồ sơ GOV-P1 gửi xem xét - Bản nháp v1

Status: `DRAFT_FOR_INSTITUTIONAL_REVIEW`

Tài liệu này chưa phải hồ sơ đã nộp, quyết định phê duyệt hay lời mời người
tham gia. Không được dùng để thu dữ liệu khi các trường quyết định bên ngoài
còn trống.

## Mục tiêu và giới hạn

Nghiên cứu đánh giá các sự kiện tư thế **quan sát được** trong phiên thi mô
phỏng và khả năng giảm cảnh báo sai. Hệ thống không xác định danh tính, suy
luận ý định/gian lận hay đưa ra quyết định kỷ luật tự động. Mọi tín hiệu cần
con người xem xét.

GOV-P1 chỉ diễn tập withdrawal và xóa bốn file tổng hợp trong thư mục tạm do
runner tạo. Rehearsal không sử dụng camera, người thật, consent thật, raw video,
mạng hoặc export. Production reconciler chưa được triển khai.

## Tài liệu đính kèm theo hash

| Tài liệu | SHA-256 |
| --- | --- |
| Đề cương canonical | `2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5` |
| GOV-P0 manifest | `c748548325c26fafcefa0543867e706ecb2064292fa591e6b4609de0e2402025` |
| Thông tin người tham gia - bản nháp | `ff2687d32f55bac9e00f9944c5db86d24d2d2480dee9cdca87241b76729c5c05` |
| Phiếu đồng ý - bản nháp | `eaa0aaa651b3b4ca8778e0f5aa1b48c4663489cf9a4af880b661d57d627b5a71` |
| External gates template GOV-P0 | `3c09e8619aeec8469837fbf9206040d991a2d1ef19ff2a99957fdc78c393f3e9` |

## Dữ liệu và giảm thiểu

- Dự kiến lưu video phần thân trên cục bộ; không thu âm thanh hay nhận diện
  khuôn mặt.
- Identity mapping và consent có chữ ký nằm ngoài dataset tree.
- Export phân tích chỉ được dùng allowlisted pseudonymous envelope; raw video,
  danh tính và operator audit không được đưa lên Colab.
- Rút lại phải chặn thu mới/export và tạo đối soát cho toàn bộ lineage.

## Quyết định bắt buộc trước người thật

| Quyết định | Trạng thái hiện tại |
| --- | --- |
| Mã phê duyệt và đơn vị/người chịu trách nhiệm | `NOT_ISSUED` |
| Phiên bản thông tin người tham gia và consent | `NOT_APPROVED` |
| Thời hạn hoặc chính sách lưu trữ | `UNDECIDED` |
| Storage root được phê duyệt | `NOT_APPROVED` |
| Encryption và ACL trên môi trường thực | `NOT_VERIFIED` |
| Đầu mối tiếp nhận yêu cầu rút lại | `UNASSIGNED` |

## Giới hạn bằng chứng rehearsal

Receipt cấu trúc hợp lệ chỉ chứng minh luồng synthetic đã chạy đúng contract.
Nó không chứng minh tính đầy đủ pháp lý của consent, phê duyệt học thuật,
storage controls thực, production deletion, camera readiness hay hiệu quả mô
hình. Các quyết định trên phải do đơn vị có thẩm quyền ban hành và ghi nhận ở
artifact phiên bản mới; không sửa template này để tự cấp quyền.
