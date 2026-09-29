# DataTalk evaluation — api

Date (UTC): 2026-09-28T01:03:19+00:00
Dataset reference date: 2026-09-28
Split: heldout
Cases scored: 2

- Answerable correctness: 0/2
- Clarification/abstention: 0/0
- Security denial: 0/0
- End-to-end latency: p50 3203.81 ms, p95 30050.9 ms (n=2)
- Query latency: p50 2350.1 ms, p95 2350.1 ms (n=1)

## Failures

- DT-006 (standard_aggregation): all: expected 52965364, observed 495471670, tolerance 52965.364
- DT-007 (standard_aggregation): expected completed answer; got failed: evaluation timeout waiting for terminal analysis status
