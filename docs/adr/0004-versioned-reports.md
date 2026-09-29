# ADR 0004 — Versioned report evidence

Status: accepted, 2026-09-28.

Store every saved result and refresh as an immutable report version with its SQL, typed plan, result, chart, and snapshot identity. This makes reopening reproducible even if source rows change. The tradeoff is retained result storage, bounded by row caps and a configurable retention policy. Exports must use the stored version, not silently recompute.
