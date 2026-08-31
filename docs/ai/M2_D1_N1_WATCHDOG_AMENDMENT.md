# M2 D1-N1 Watchdog Amendment

Status: implementation candidate; device execution remains NO-GO until independent review.

## Outcome contract

The public fixed preflight consumes schema-v2 authority in the parent before any worker or
device work. Capture, FFmpeg, DirectShow, the two raw frame buffers, and synchronous
MediaPipe inference run only inside one suspended worker assigned to a Windows Job Object.
The parent owns the watchdog and is the only process that finalizes terminal authority.

## Time boundaries

- Worker startup and first complete frame: at most 20 seconds.
- Evidence window: 60 seconds from the actual complete-frame ingress timestamp recorded by
  `_FrameReader` and passed unchanged through worker IPC; queueing or scheduling delay consumes
  this same window. Capture closure carries the platform timestamp taken after cleanup completes.
- There is no post-window inference or cleanup margin.
- Final aggregate report after confirmed capture close: at most 5 seconds, but only after
  capture has closed inside the hard 60-second evidence boundary.

A worker that does not report confirmed capture closure inside the hard 60-second boundary
is terminated with its descendants and cannot pass.

## Trust and privacy boundaries

- Worker executable path, module, argv, System32 working directory, and environment are fixed;
  SystemRoot, WINDIR, and PATH derive only from the Win32-resolved system directory.
- The worker executable is deny-write/delete leased and image-verified before resume.
- A challenge-named Job Object uses JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE and an active-process
  limit of two. Before device work the worker verifies its own membership and both policies;
  breakaway is not requested.
- PowerShell camera enumeration resolves System32 through GetSystemDirectoryW, deny-write/delete
  leases the executable and ancestors, verifies the suspended process image, uses a System32
  working directory, and supplies a PATH containing only protected system folders.
- IPC is canonical bounded JSON containing lifecycle events and aggregate receipt evidence.
- The worker receives only the four prepared FFmpeg binding values. It creates surrogate local
  token/nonce values and cannot access the real authority store.
- After authority becomes CONSUMED, the parent persists a strict, expiring, nonsensitive
  WorkerGrant bound to the challenge, consumed-authority digest, source/lock/model/FFmpeg
  bindings, worker image identity, fixed argv, and Job policy.
- Both the runner and worker independently require the exact `ISSUED` grant from the fixed
  LocalAppData location resolved by the Windows shell API. A self-minted grant/capability pair
  without durable issuance after the real CONSUMED transition stops before worker-image lease,
  enumeration, MediaPipe construction, or camera access. The worker uses a grant-only reader and
  has no API or path to the private prepared-authority record.
- A fresh 256-bit capability is persisted only as a digest. Its secret crosses only an anonymous
  inherited stdin pipe created with close_fds enabled for the exact suspended worker. The worker
  blocks before enumeration, validates the grant and capability, then emits AUTHORIZED. Named
  Job membership or readable grant data alone cannot authorize device work.
- The real authority token, authorization nonce, device name/path, executable path, frames,
  model bytes, screenshots, URLs, and raw artifacts are not transmitted in worker IPC.
- Parent reconstructs protected receipt, privacy, cleanup, seal, and provenance fields from its
  consumed authority and fixed contract, and validates every PASS or NO_GO candidate.
- Worker NO_GO measurements are discarded; the parent issues minimal failure evidence from only
  the typed outcome/failure plus parent-observed cleanup and supervision state.
- A receipt is eligible only after graceful Job drain, closed IPC, a stopped reader, worker exit
  code zero, prior AUTHORIZED evidence, worker lease closure, and Job-handle closure. Forced
  termination can never pass.

## Fail-closed behavior

Blocked face or pose inference cannot block the parent. At deadline the parent terminates the
entire Job Object, requires zero active processes, closes IPC and the executable lease, emits
typed PRIVACY_GUARD_TIMEOUT, and persists terminal authority. There is no retry path.

If job termination, graceful process drain, zero exit, IPC closure, worker lease cleanup,
receipt parsing, or candidate semantics cannot be proven, the result is NO_GO; no
D1_N1_PREFLIGHT_PASS is issued.

The capability boundary covers unauthorized application call paths. It does not claim isolation
from debugging, injection, or handle theft by a hostile process already running as the same
Windows account; that stronger threat model requires a broker under another security principal.

## Acceptance before device access

- Focused test must block face and pose separately and prove worker plus dummy descendant exit.
- Adversarial tests must reject a PASS payload followed by a hang or nonzero exit.
- A worker without the inherited capability must fail before platform or MediaPipe construction.
- Shadow PATH/CWD and mutated NO_GO fields must not cross the parent trust boundary.
- The terminal receipt must be durable and the consumed authority must reject retry.
- Ruff and mypy must pass on the current revision.
- Sol must independently approve the source and observed no-device Job Object capability.

This amendment does not authorize camera execution, participant use, audio, deployment,
release, device_gate_decision, or D1_GO.
