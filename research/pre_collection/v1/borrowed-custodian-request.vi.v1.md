# Checklist đề nghị hỗ trợ máy custodian - v1

Status: `NO_EXECUTION_AUTHORITY`

Tài liệu này chỉ mô tả nhu cầu trong tương lai; không phải yêu cầu chạy ngay,
không chứa credential và không cấp authority.

## Nhu cầu tối thiểu

- Một máy vật lý Windows 11 x64 không phải máy preflight.
- Một tài khoản local standard-user dành cho ceremony.
- Có thể ngắt mạng, tắt cloud sync và không sao lưu private key.
- Khoảng thời gian dự kiến 30 phút để kiểm tra môi trường, xác minh public kit,
  thực hiện đúng một ceremony đã được cấp quyền riêng, và kiểm tra receipt.

## Stop conditions

- Không có custodian chịu trách nhiệm hoặc máy không đáp ứng điều kiện.
- Tool, manifest, RP2 triple, epoch, provider hoặc scope lệch authority.
- Có network adapter `Up`, quyền elevated/admin, reparse root, key cùng tên,
  retry, overwrite, backup, private export hoặc target-workstation use.
- Chưa có fresh exact B0.3 execution authority.

Nếu các điều kiện sau này được đáp ứng, operator vẫn phải dừng sau sanitized
B0.3 receipt và xin authority B0.4 riêng. Checklist này không đặt lịch, không
cam kết có máy và không cho phép chạy vật lý.
