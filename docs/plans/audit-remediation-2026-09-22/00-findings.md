# Consolidated findings — 2026-09-22 audit

Four read-only audit passes (security/privacy, spec compliance, test/code
quality, packaging/docs/delivery) plus direct verification. IDs are stable
references used by the task files. No finding was discovered to be CRITICAL.

Legend: Sev = severity at audit time. State = audit evidence label.

## HIGH

| ID | State | Finding | Location |
|----|-------|---------|----------|
| H1 | OBSERVED | `scripts/build_release.ps1` builds stale `packaging/PDU-Exam-Observer.spec` (`hiddenimports=[]`, datas = `assets/web`+`demo` only). A rebuild today produces a bundle missing `assets/models`, mediapipe/onnxruntime data files, and `tools/ffmpeg.exe` — it cannot reproduce verified candidate-06. `tests/packaging/test_release_pipeline.py:16` pins the spec name. | scripts/build_release.ps1:43; packaging/PDU-Exam-Observer.spec:31-32 |
| H2 | OBSERVED | `THIRD_PARTY_NOTICES.txt` (15 lines, shipped verbatim in candidate-06) lists only FastAPI/Uvicorn/React/Vite/PyInstaller. The bundle actually contains mediapipe (Apache-2.0 + bundled third-party), onnxruntime (MIT), onnx (Apache-2.0), numpy (BSD), opencv-python, pydantic, starlette, anyio, sse-starlette, click, certifi (MPL-2.0), sounddevice + PortAudio, setuptools vendored wheels, python311 (PSF), ffmpeg.exe (LGPL — covered separately by FFMPEG_LICENSE.txt but absent from notices). File self-discloses the generated inventory was never attached. Hard gate before any distribution. | THIRD_PARTY_NOTICES.txt |
| H3 | OBSERVED | `apps/web/package.json` pins every dependency as `"latest"`; reproducibility rests solely on `package-lock.json` + `npm ci` discipline in `build_release.ps1:24-30`. Any plain `npm install` silently upgrades the toolchain. | apps/web/package.json:14-32 |
| H4 | OBSERVED | The entire M2–M7 delivery exists only in the uncommitted working tree of `codex/complete-system-colab` (59 modified + 36 untracked at audit time, incl. `research_runtime/`, `showcase/`, `workspace_service.py`, `api/workspace.py`, `tests/runtime/`, `tests/training/`, `research/training/`). Consistent with "no commit" policy, but a lost checkout destroys the delivered source; `SOURCE_MANIFEST.json` inside candidate-06 is the only byte-level provenance. | git status; .git/HEAD |
| H5 | OBSERVED-as-documented | External acceptance gaps (recorded honestly, still binding): GAP-08 clean-machine UNVERIFIED/user-deferred; current camera ~10.08 fps < required 15 fps → REAL capture fails closed; one physical display vs required ≥2; institutional approval NOT_PERFORMED; training evidence is `SYNTHETIC_SMOKE` only — no research performance, no calibration-quality evidence. | docs/ai/CURRENT_TASK.md; output/completion-2026-09-08/workspace-camera.json |

## MEDIUM

| ID | State | Finding | Location |
|----|-------|---------|----------|
| M1 | SOURCE_VERIFIED | Collection authority is document-hash-bound, not signed: an operator can write a well-formed `collection-authority.v1.json` over locally chosen files and collect. Correct within the declared threat model (same-account attacker excluded; disclosed in `service.py:137-142` and `WORKSPACE_GUIDE_VI.md:58-62`) but not named in `RISK_REGISTER.md`. Also: `chmod 0o700` in `authority_cli.py:196` is a no-op for Windows ACLs — do not present it as a control. | research_runtime/authority_cli.py:147-218 |
| M2 | SOURCE_VERIFIED | (a) No technical interlock between workspace collection authority and the D1 device-gate rung ladder — `start_real_collection` substitutes its own preflight+authority; ordering is procedural only. (b) `m2research` does not re-verify storage encryption/ACL at start (`launcher.py:81-82` hardcodes UNVERIFIED) — assurance is delegated to authority issuance time. | research_runtime/service.py:433-462,998-1027; launcher.py:81-84 |
| M3 | OBSERVED | `_ffmpeg_path` falls back to `shutil.which("ffmpeg")` without hash verification when the bundled binary is absent (contrast: PowerShell/worker images are fingerprint-verified in `m2_d1_native.py:3343-3351`). | research_runtime/service.py:1627-1632 |
| M4 | OBSERVED | Stale docs: `ARCHITECTURE.md` describes two modes (actual: five — `launcher.py:43`); `PACKAGING_DISTRIBUTION.md` describes the old `PDUExamObserver.exe` bundle shape, not `PDU-Workspace`/`_internal`/`START.cmd`/`HUONG_DAN.md`/`SOURCE_MANIFEST`/`DELIVERY_MANIFEST`; `README.md` milestone+repo map predate M2–M7; `pyproject.toml` description says "M1 governance persistence"; `demo/README.md` claims the fixture adapter "is not connected" though `services/core.py:389-404` wires `/api/v1/demo/replay`. `TRACEABILITY_MATRIX.md` has no spec→code layer for ~60% of the codebase (`research_runtime/`, `showcase/`, `workspace_*`, `m2_*`). | docs/architecture/ARCHITECTURE.md; docs/spec/PACKAGING_DISTRIBUTION.md:13-25; README.md:7-28; demo/README.md:9-13 |
| M5 | OBSERVED | Candidate/handoff hygiene: `candidate-04` (partial) and `candidate-05` (complete but different source state) carry no SUPERSEDED marker and are easily confused with verified candidate-06; four `packaging/handoffs/m2-s3e-failed-*` + `m2-s3e-diagnostic-fourth` trees contain runnable-looking payloads; `packaging/release/` + `packaging/README.txt` describe the historical M1 bundle without a HISTORICAL banner. | packaging/candidates/completion-2026-09-08/; packaging/handoffs/; packaging/release/ |
| M6 | OBSERVED | `tests/training/test_notebook_contract.py:30-31` regenerates checked-in artifacts (`preprocessing_golden.npz`, `pdu_stgcn_training_colab.ipynb`) in-tree and validates the fresh output — committed-artifact drift is masked. | tests/training/test_notebook_contract.py |
| M7 | OBSERVED | `service.py:1634-1653` reads all of `pose_timeline.jsonl` into memory before hashing/parsing — no size cap at this read site (contrast bounded reads in `model_import.py:78-113` and evidence scripts). | research_runtime/service.py:1634-1653 |
| M8 | OBSERVED | Unbounded SSE subscriber queues (`services/core.py:316-318` `asyncio.Queue()`; fan-out `:105-106`; subscriber list `:99,317`; same fan-out inherited by M1 `m1.py:684-685`) and unbounded `SessionRecord.events`/`answers` in `repositories/in_memory.py:18,55-61`. M0/demo path primarily; M1 persists history in SQLite but per-subscriber queues remain unbounded. | services/core.py; repositories/in_memory.py |
| M9 | OBSERVED | `authority_cli.template_main` exists (`authority_cli.py:231-271`) but `__main__.py` exposes no `authority-template` route; packaged operators cannot generate the record template as `WORKSPACE_GUIDE_VI.md:66` implies. | src/pdu_exam_observer/__main__.py; research_runtime/authority_cli.py |
| M10 | SOURCE_VERIFIED | Withdrawal sets `external_export_follow_up_required` flag when exports exist but creates no task rows — unlike M1 `withdrawal_tasks`. Derived-copy follow-up is a flag, not a ledger. | research_runtime/service.py:883-895 |
| M11 | SOURCE_VERIFIED | Schema/field gaps vs spec: no `consent_receipt_id`/`consent_version` in the runtime authority record (M1 API has them, `contracts.py:89-91`); no operator/reviewer attribution on `runtime_reviews`/`runtime_exports`; `focus.contaminated_by_operator` emitted as constant `False` (`service.py:1711`) — dead field; dropped-frame counter discarded (`service.py:597`), gaps ≤45 frames silently repeat last frame (`:1365-1377`) — no persisted drop accounting; `runtime_sessions` lacks `protocol_version` (`service.py:266-275`); runtime timeline rows lack `processing_status`/`processed_ns`. | research_runtime/service.py |
| M12 | OBSERVED | Missing discriminating tests: REAL `_native_preflight` path (`service.py:975-996` — tests inject `diagnostic_provider=lambda: REAL_PREFLIGHT`, `test_research_runtime.py:50`); frozen-rules↔authority binding (`service.py:1113-1129`); `QUARANTINE_RUNTIME_ARTIFACTS` withdrawal branch (`service.py:881-882`); workspace negative-auth on `/workspace/*`; `workspace_cli.py`/`__main__` dispatch; `research/training/showcase/v3/cli.py` RESEARCH gate; calibration math (smoke-only today). | tests/ |

## LOW

| ID | State | Finding | Location |
|----|-------|---------|----------|
| L1 | OBSERVED | Monitor binds `host="localhost"` while exam binds literal `127.0.0.1`; `localhost` may resolve to `::1`, diverging from the "literal loopback" claim and creating IPv4/IPv6 mismatch risk on some machines. `monitor_origin`/`allowed_hosts` also use `localhost`. | launcher.py:94-95,133-134 |
| L2 | OBSERVED | f-string SQL column interpolation `UPDATE runtime_sessions SET {columns}` — safe today (literal kwargs only) but fragile for future callers. | service.py:1771-1774 |
| L3 | OBSERVED | `AnswerRequest` lacks `extra="forbid"` (no impact: 64 KiB body cap + `model_dump()` fields only). | contracts.py:204-207 |
| L4 | OBSERVED | PIN throttle uses wall clock and a de-facto global bucket on loopback; monotonic window is the correct primitive. | services/core.py:54-68; factories.py:277-282 |
| L5 | INFO | No persistent reviewer login/logout audit events — weakens the audit story for a research instrument (never record PINs). | services/core.py:112-143 |
| L6 | OBSERVED | `scripts/start_workspace_preview.py` leaves a detached server + temp root (`preview-server.json`) with no companion stop/cleanup path. | scripts/start_workspace_preview.py:15-48 |
| L7 | OBSERVED | `packaging/manifest-metadata.json` (written by `build_release.ps1:78`) is not gitignored. | .gitignore |
| L8 | OBSERVED | Network guard (`m2_d1_native.py:124-194`) is Python-process-local and self-reported; native DLL egress is invisible to it. Detection belt, not a boundary — keep as is but state the limit in SECURITY_PRIVACY.md. | src/pdu_exam_observer/m2_d1_native.py |
| L9 | DERIVED | Ledger test-count skew: `QUALITY_GATES.md` (2026-08-30) records 846 backend/58 frontend; current tree has ~734 test functions + parametrization and 82 frontend tests. Milestone-versioned sections were never updated; needs one authoritative run. | docs/ai/QUALITY_GATES.md |
| L10 | PLAUSIBLE | Degenerate/empty frame → `np.var`/`np.mean` NaN → `NaN` literal in canonical JSON (invalid strict JSON, self-consistent since same bytes are hash-bound). Edge case only. | research_runtime/service.py:~1057-1059 |
| L11 | OBSERVED | Candidate-06 rebuild not fully reproducible from repo: `build_completion_delivery.py` needs external `--build-python`/`--ffmpeg`; pinned build env `output/.../package-env` no longer exists; FFmpeg provenance is hash-only (`M2_D1_NATIVE_ASSET_PROVENANCE.md:89`); PyInstaller 6.10.0 pinned only in `build_release.ps1:33`, not in the completion builder. | scripts/build_completion_delivery.py |
| L12 | OBSERVED | `RESEARCH_COLLECTION_NOT_IMPLEMENTED` (`m1.py:1105`) is correct for the M1 store but semantically stale at product level — collection IS implemented in the workspace path of the same binary. | m1.py:1105,1124-1126 |
| L13 | OBSERVED | `configuration.py` forbidden-root set still lists `_archive/` which no longer exists — harmless stale defense. | configuration.py |
| L14 | OBSERVED | `test_release_pipeline.py` asserts source-text properties of `build_release.ps1`; behavioral test skips unless Windows+built exe+PowerShell — expected, but means script regressions are caught only statically. | tests/packaging/test_release_pipeline.py:10-34 |

## Verified OK (no action)

Dual-origin separation with exact Host/Origin matching; scrypt PIN +
digest-only single-active bearer with dual-clock expiry; `extra="forbid"` +
`Literal` whitelists on workspace models; server-derived paths with
reparse/hardlink/NFC/reserved-name defense; exact-allowlist ZIP import/export
with compression-ratio caps; no pickle/yaml/eval/exec/innerHTML; fixed-argv
ffmpeg with `-nostdin -an`; per-frame authority revalidation; fail-closed
camera/pose/focus/model/encoder/disk/schema/clock; single camera owner (unique
index + thread liveness + RootLease); destructive reconciliation unreachable
over HTTP (permanent 403); export emits exactly the 14-field allowlist;
canonical sorted-key JSON; governance hash chain P0→P1→P2 consistent; drafts
marked DRAFT_*; zero TODO/FIXME markers repo-wide; all pyproject runtime deps
exact-pinned with Windows x64 wheels present in uv.lock.
