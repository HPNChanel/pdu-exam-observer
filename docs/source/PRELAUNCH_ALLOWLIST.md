# Observed prelaunch allowlist

Status: read-only inventory contract. The former source path is historical; its disposition is `OBSERVED_BEFORE_ARCHIVE`, and its current archive location is `OBSERVED_CURRENT_ARCHIVE`.

The prelaunch root is `D:\FOR_RESEARCH\SCIENTIFIC_RESEARCH`. The recorded allowlist is:

- `pdu-exam-observer\` - the current project directory.
- `outputs\ĐỀ CƯƠNG CHƯA CHÍNH THỨC.docx` - the original source input, `OBSERVED_BEFORE_ARCHIVE`; absence at the old root is expected after the approved scoped move.
- `pdu-exam-observer\_archive\prelaunch-2026-08-24\outputs\ĐỀ CƯƠNG CHƯA CHÍNH THỨC.docx` - the current archived original, `OBSERVED_CURRENT_ARCHIVE`, and the required hash witness for the former root input.
- `pdu-exam-observer\docs\source\DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx` - the canonical project copy, `SOURCE_VERIFIED`.

The allowlist records observed paths and the approved disposition; it does not authorize any new deletion or movement. G0 fails only when the canonical copy or required archive witness is missing, the canonical/archive hash does not match, or an unexpected current root path violates the allowlist. Absence of the former `outputs\...docx` path after the approved scoped move is expected, not an unexpected root item. The checker must stop without deleting, overwriting, or archiving an unexpected item.
