# Security and Privacy Specification

Version: 1.0

## Threat boundary

The MVP protects against accidental exposure, a participant navigating to reviewer routes, cross-site browser requests to localhost, unsafe browser input reaching filesystem or process execution, packaging mistakes, and untracked exports.

The MVP does not claim protection against malware, an attacker controlling the same Windows account, physical disk access outside the encrypted-volume boundary, or compromise of an external Google account after export.

## Origin and role separation

Exam and monitor run on separate dynamically selected loopback ports in one Python process. The exam host is `127.0.0.1`; the monitor host is `localhost`. The launcher binds the exam to IPv4 loopback and the monitor to localhost loopback. Each ASGI app exposes only its permitted routes.

Reviewer login uses a configured local PIN verified against a slow password hash. Candidate pairing uses a random, single-use, short-lived code created by the reviewer. Candidate authentication is a host-only `HttpOnly` cookie plus CSRF at exam host `127.0.0.1`; the reviewer is not cookie-authenticated. Reviewer login returns an opaque 256-bit bearer exactly once; only its digest is stored server-side; one active bearer is allowed; and replacement, logout, or expiry revokes it and every bound issued reconciliation challenge after a fixed two-hour TTL. Wall time remains the audit/display timestamp, while the live bearer and challenge TTLs are also bounded by process-monotonic elapsed time. Non-finite timestamps, backwards clocks, expiry during planning or lock acquisition, and reviewer-session change before the final issue/consume transaction fail closed. One backend owns one active confirmation-service revocation callback; service replacement supersedes the stale callback.

The current contract is `OBSERVED` by the backend/frontend code gates. The monitor stores the reviewer bearer only in versioned monitor-origin `sessionStorage`, attaches it at request time in `Authorization`, uses `credentials: omit`, validates it after reload, and clears it on `401`. The bearer never enters a URL, cookie, `localStorage`, DOM, or logs. Authenticated POST fetch-stream SSE revalidates the bearer on every event/heartbeat; native `EventSource` is not used.

Every state-changing HTTP request requires:

- authenticated role;
- exact allowed Origin;
- allowed Host;
- CSRF token bound to the session;
- content-type validation;
- request-size limit;
- resource ownership and current-state check;
- idempotency handling where duplicate user actions are plausible.

SSE is reviewer-only, authenticated, Origin-checked, push-only, rate-bounded, and resumable by event sequence. It is opened by an authenticated POST fetch-stream request and revalidates the bearer on every event/heartbeat. Candidate capabilities cannot access reviewer events, media, exports, model import, or session administration.

Same-context fresh-tab browser behavior is `OBSERVED` in packaged Chromium: tab A authentication survives reload; fresh tab B navigation shows the PIN and receives `401` without a bearer; tab A remains authorized. Accepted `UNVERIFIED` residuals are same-origin XSS reading the bearer, duplicate-tab/session-restore copying it, and the candidate cookie lacking `Secure` on plain HTTP loopback. Other browsers, physical devices/two-display behavior, clean-machine behavior, signing, deployment, and external release evidence remain `UNVERIFIED`.

## Browser controls

Default response headers include Cache-Control: no-store, Content-Security-Policy with default-src self and frame-ancestors none, X-Content-Type-Options: nosniff, Referrer-Policy: no-referrer, and restrictive Permissions-Policy.

No wildcard CORS is enabled. The frontend contains no remote script, font, image, frame, analytics, or telemetry endpoint.

## Native and filesystem controls

Run as a standard user. Do not install a service, request elevation, or execute shell commands from HTTP input.

Enumerate cameras and displays server-side. Browser input selects opaque IDs from the current enumeration. It cannot provide paths, URLs, commands, model locations, export destinations, executable names, or device identifiers.

Raw video is never mounted as a static directory and is never returned by an arbitrary path. Authorized review requests resolve an opaque artifact ID through the repository, verify ownership and state, and stream with no-store headers.

The Python-level outbound-socket guard used by the native device-validation paths observes only sockets created inside the process that installs it; it cannot observe egress by native libraries (cv2, mediapipe, onnxruntime, FFmpeg). It is a detection aid, not an egress boundary — the actual boundary is that no code path performs network egress at all.

Logs exclude video frames, landmark arrays, names, tokens, cookies, PINs, URLs, window titles, process names, local usernames, full paths, and exported record bodies.

## Failure behavior

Camera, encoder, disk, pose, focus, model, schema, clock, and event-delivery faults become explicit technical states. They never silently convert to NORMAL.

Start and stop are serialized. Session sealing validates artifacts and commits atomically. Duplicate start, stop, answer, and submit requests return the original result when the idempotency contract matches.

## Release integrity

Dependencies, task models, FFmpeg, ONNX bundles, and frontend assets are pinned and included in checksums. Releases include third-party notices and an identical detached copy of the bundled `RELEASE_MANIFEST.json` beside the ZIP; its SHA-256 is published separately when distribution begins. The detached and bundled manifests must compare byte-for-byte and by SHA-256.

Unsigned trial packages may trigger Windows warnings and are not tamper-resistant. Authenticode is a later release gate, not an M0 claim.
