# ADR 0003 — Synthetic fast/full profiles

Status: accepted, 2026-09-28.

Generate a small fast profile at demo startup and a deterministic full profile for acceptance and performance checks. Both use the same schema and generator with fixed seed/reference date. This avoids committing large generated files or making paid model calls for bulk data. Fast-profile performance and accuracy cannot stand in for full-profile measurements.
