# ADR 0002 — Typed plan and bounded SQL

Status: accepted, 2026-09-28.

Interpret a question into a validated analytical plan and compile from a known semantic catalog. Parse the resulting SQL AST and run it with a dedicated read-only role against workspace-scoped views. This favors explainable, auditable answers over arbitrary SQL flexibility. The supported question space is intentionally constrained to the Northstar schema; unsupported requests require clarification or abstention.
