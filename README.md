# PDU Exam Observer

PDU Exam Observer is a local-first Windows research instrument for studying observable webcam events during a mock computer-based examination. It records consented sessions, extracts pose landmarks, generates real-time evidence for a reviewer on a second monitor, and supports reproducible comparison between rules, camera-only inference, and context-aware inference with abstention.

The system does not identify people, infer intent, decide that cheating occurred, or apply discipline. Its operator outputs are limited to NORMAL, REVIEW_REQUIRED, and TECHNICAL_INSUFFICIENT.

## Current state

As of 2026-09-08 the technical delivery is `LOCAL_TECHNICAL_DELIVERY_VERIFIED`
(`docs/ai/COMPLETION_2026_09_08.md`): the M2–M7 workspace path — capture,
pose, focus, review, export, withdrawal, model import/inference, and
evaluation code — plus a self-contained Colab training package are implemented
and verified locally with synthetic evidence and a same-host packaged run.
The operator UI is Vietnamese (`docs/WORKSPACE_GUIDE_VI.md`).

External gates remain open and are recorded honestly: no institutional
approval, consent, retention, or storage authority has been issued; no real
participant has been collected; the current camera (~10 fps measured) and
single-display host fail closed below the required 1280x720 @ 15 fps +
two-display profile; clean-machine verification is deferred; no research
performance is claimed.

## Historical milestones

M1 extends the locally verified M0 foundation with a pre-collection governance path:

- canonical proposal provenance;
- decision-complete product, research, data, model, security, and packaging specifications;
- a Python/FastAPI backend skeleton;
- a React exam and reviewer demo;
- deterministic real-time event replay without webcam or model claims;
- a Windows portable one-directory packaging path;
- SQLite-WAL persistence for studies, pseudonymous participants, sessions, answers, events, and audit records;
- native-only approved-root configuration outside the application bundle;
- reviewer workflows for retention records, operator consent confirmation, recovery, and participant-wide withdrawal.

Institutional approval cannot be granted from the browser, and M1 research sessions cannot enter recording. Camera capture, real participant collection, model training, and confirmatory evaluation remain gated by later milestones.

GOV-P0 adds a zero-cost, machine-verifiable pre-collection pack under
`research/pre_collection/v1/`: source traceability, draft method/label/scenario
contracts, Vietnamese information and consent drafts, external-gate tracking,
and deterministic validation. Its successful receipt explicitly keeps research
readiness and collection authorization false. B0.3 remains deferred because no
suitable custodian device exists; it is not bypassed.

GOV-P1 adds a synthetic-only withdrawal/deletion rehearsal under
`research/pre_collection/gov_p1/v1/`. It reuses the real M1 metadata contract
but creates and deletes only fixed fixtures in a runner-owned temporary root.
The resulting EthicsDataReceipt proves the rehearsal invariants, not production
deletion: M1 withdrawal tasks remain pending and institutional, storage,
retention, camera, participant, and collection gates remain closed.
Its reviewed source files are hash-pinned and generated outputs are replaced
atomically. It deliberately does not claim production-grade deletion against a
hostile process running concurrently under the same local account.

## M1 local configuration

The default runtime remains the deterministic `m0` demo. To prepare the `m1` metadata store, configure an absolute local NTFS directory through the native entrypoint. Record `VERIFIED` only when the corresponding storage control has actually been checked; otherwise keep `UNKNOWN`, which remains a blocking readiness gate.

~~~powershell
uv run python -m pdu_exam_observer configure --root "D:\PDU-Research-Data" --encryption-status UNKNOWN --acl-status UNKNOWN
$env:PDU_RUNTIME_MODE = "m1"
$env:PDU_REVIEWER_PIN = Read-Host "PIN reviewer" -MaskInput
try {
    uv run python -m pdu_exam_observer
}
finally {
    Remove-Item Env:PDU_RUNTIME_MODE -ErrorAction SilentlyContinue
    Remove-Item Env:PDU_REVIEWER_PIN -ErrorAction SilentlyContinue
}
~~~

Configuration is stored under `%LOCALAPPDATA%\PDUExamObserver\config.v1.json`. Browser input never selects a filesystem path. Identity mappings, signed consent material, media, and exports remain outside the application and outside source control.

## Repository map

~~~text
apps/web/                  React exam and reviewer surfaces
src/pdu_exam_observer/     Python domain, API, runtime, and launcher
research/                  Pre-collection governance packs, institutional
                           submission drafts, and training/Colab code
demo/                      Non-personal deterministic fixtures
tests/                     Backend, runtime, training, packaging, and research
packaging/                 PyInstaller and release assembly
scripts/                   Local development and verification commands
docs/source/               Immutable proposal and provenance
docs/spec/                 Binding product and research specifications
docs/architecture/         Runtime architecture and decisions
docs/plans/                Roadmap, implementation plan, gates, risks
docs/ai/                   Current task and stable outcome contract
~~~

## Development principles

The application is offline by default, binds only to literal loopback, stores research data outside the replaceable application bundle, and never ships personal data. Demo data is clearly marked. All research samples retain provenance, including whether they are real, AI-rendered, or augmented.

Development commands are defined by pyproject.toml, apps/web/package.json, and scripts. Exact dependency versions are locked during M0 and become revision-scoped evidence rather than assumptions in this README.
