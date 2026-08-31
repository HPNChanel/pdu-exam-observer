# Data Governance Specification

Version: 1.0

## Data classes

Restricted identity: participant name, contact information, signed consent, withdrawal request, and mapping to pseudonymous participant code.

Restricted media: raw or derived video frames and authorized local review clips.

Sensitive research data: pose landmarks, timing, labels, quality metrics, focus enums, predictions, reviewer decisions, and model provenance.

Non-personal project data: source code, schemas, synthetic demo fixtures, empty templates, documentation, and release assets.

## Storage topology

Application bundle: replaceable and read-only in normal operation. It contains code, static frontend, approved task/model assets, schemas, demo fixtures, notices, and checksums. It contains no real participant data.

Research data root: an operator-selected local NTFS path protected by current-user ACLs and an approved encrypted volume such as BitLocker or Device Encryption. The app must not invent custom video encryption.

Identity root: a separately controlled encrypted location outside the dataset tree. The application stores only consent receipt ID, consent version, confirmation time, and withdrawal state.

Export staging: a new directory per export, written from an allowlist, verified, hashed, sealed, and then explicitly transferred by the operator.

## Consent and start gate

Real capture is prohibited until the session has:

- pseudonymous participant code;
- consent receipt and version;
- confirmation by an authorized operator;
- approved research data root;
- recorded retention decision;
- passing camera, disk, encoder, display, and focus preflight.

The participant can withdraw before or after a session. Withdrawal changes the session state, blocks new export, and creates a deletion/reconciliation task for every derived bundle and Colab copy.

## Data minimization

Do not collect audio devices, face embeddings, identity features, keystrokes, clipboard content, network traffic, full executable paths, process names, window titles, URLs, browser history, or unrelated screen content.

Store focus as an enum and timestamps only. Store image quality as numeric measures or approved enums. Do not store diagnostic frames in ordinary logs.

## Export allowlist

Allowed:

- pseudonymous study, participant, session, and segment IDs;
- normalized pose landmarks and visibility;
- monotonic and relative timestamps;
- approved research labels and reviewer state;
- image-quality values;
- exam-focus enum and signal age;
- source_kind and parent provenance;
- split assignment;
- schema, preprocessing, and capture versions;
- bundle manifest and hashes.

Forbidden:

- video, image, audio, thumbnails, or encoded frames;
- participant name, email, phone, signature, consent image, or mapping;
- local filesystem paths, machine username, device serial, IP address, token, cookie, or secret;
- window title, URL, browser history, process name, executable path, or command line;
- arbitrary attachments or user-selected directories.

## Retention

The project does not invent a legal retention period. A collection cannot start until an authorized operator records a retention end date or approved retention policy reference. The system must support identifying all artifacts derived from a participant so that withdrawal and scheduled deletion are auditable.

Deletion is fail-closed: resolve exact paths under the approved data root, enumerate manifest-owned artifacts, verify hashes where available, and require an explicit operator confirmation. Never accept a deletion path directly from browser input.

## Incident response

On suspected leakage, stop collection and export, preserve non-sensitive audit evidence, identify affected manifests and destinations, notify the responsible researcher, and follow institutional procedure. Do not silently reclassify or delete evidence to conceal an incident.

