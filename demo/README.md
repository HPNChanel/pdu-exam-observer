# Deterministic M0 demo fixture

`events.jsonl` is a schema-neutral, synthetic event stream for packaging and
replay plumbing. It contains no person, identity, camera frame, landmark, or
media data. `event_seq` is strictly increasing and `occurred_at_ms` is fixed.
Every event has `confidence: null` and a typed `confidence_status`; null is not
silently interpreted as a numeric confidence.

The exact runtime event parser is owned by the integration work and is not
assumed here. The remaining integration hook is an adapter that maps this
JSONL fixture into the app's documented demo-replay input contract. Until that
adapter is connected, this fixture is packaging evidence only, not runtime
replay evidence.
