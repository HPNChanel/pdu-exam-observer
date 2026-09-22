# PDU ST-GCN Colab training and restore guide

This delivery is self-contained. The notebook embeds the training and runtime
contract source and installs only the versions pinned in
`requirements-colab.txt`.

## Synthetic smoke

1. Upload `pdu_stgcn_training_colab.ipynb` to Colab.
2. Leave `MODE = 'SYNTHETIC_SMOKE'` and run all cells.
3. Download the model and report ZIPs. The model ZIP is always marked
   `DEMO_ONLY_NOT_RESEARCH_PERFORMANCE`.

`fixtures/synthetic_smoke_input.npz` records the deterministic tensor, label,
context, participant, provenance, and seed inputs used by the smoke generator.
Its manifest binds the fixture hash. It is synthetic plumbing evidence only.

## Research mode

Set `MODE = 'RESEARCH'`, `RESEARCH_EXPORT` to a local pose-only runtime export,
and `PROTOCOL_FREEZE` to a self-hashed frozen protocol. Never upload raw video,
identity mappings, operator audit data, names, window titles, or process names.
Pilot data and generated data cannot enter calibration or test folds.

The protocol template intentionally contains null thresholds. Select and freeze
them from the approved pilot or calibration procedure before any outer-test
evaluation. Local execution does not establish academic approval or research
performance.

## Restore and import

Re-running the notebook restores its embedded source into
`/content/pdu-training`; it does not clone or execute remote code. Preserve both
downloaded ZIPs. Import the model ZIP unchanged through the Workspace model
import flow. The importer admits exactly eight files, verifies every checksum,
rejects ONNX external tensor data, runs ONNX/golden parity on CPU, and only then
switches the active model atomically. Keep the reports ZIP separate for human
review and provenance.
