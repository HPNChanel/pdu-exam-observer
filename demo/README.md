# Deterministic M0 demo fixture

`events.jsonl` is a schema-neutral, synthetic event stream for packaging and
replay plumbing. It contains no person, identity, camera frame, landmark, or
media data. `event_seq` is strictly increasing and `occurred_at_ms` is fixed.
Every event has `confidence: null` and a typed `confidence_status`; null is not
silently interpreted as a numeric confidence.

The fixture is wired into the running application: the monitor-origin route
`POST /api/v1/demo/replay` maps this JSONL into the demo-replay input
(`src/pdu_exam_observer/services/core.py`), and the packaged bundle ships it
as `_internal/demo/events.jsonl`. It remains synthetic demo data — not
research or camera data.
