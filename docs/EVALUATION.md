# Evaluation protocol and results

## Data and split

The fixed full scenario uses seed 4104 and reference date 2026-09-28. Generate it with `python scripts/seed_data.py --profile full` and validate it with `python scripts/validate_data.py data/generated/full`. The full CSV manifest reports 50,000 Northstar orders and 120,000 lines plus a small separate Eastwind workspace. Its generated totals across both workspaces reconcile to gross 1,138,404,231 cents, discounts 37,015,521 cents, refunds 26,056,101 cents, and net 1,075,332,609 cents. These are synthetic ledger totals, not business results.

`python scripts/generate_evals.py` generates 140 evaluation questions: 60 standard aggregations, 30 join/cohort/refund/date cases, 20 ambiguous or unanswerable cases, and 30 access/SQL-injection/resource cases. Forty are development examples and 100 are held out. Development questions use the first eight full months and first two campaigns; held-out questions use the last eight full months and last two campaigns with distinct wording. Ground truth is derived from structured source rows and kept under `evals/private`, outside the runtime catalog, indexes, and prompts. The runner compares semantic results rather than SQL strings, accounting for row order, cents/decimal tolerance, nulls, and UTC half-open periods.

The explicit edge fixture expects January net revenue 22,000 cents; February gross 5,000, discount 500, refunds 6,000, net −1,500, and AOV 4,500 cents; March AOV is null because there are no completed orders. Multiple refunds on one line are separate dated events, exposing join fan-out mistakes.

## Commands

```sh
python scripts/seed_data.py --profile full
python scripts/validate_data.py data/generated/full
python scripts/generate_evals.py
python evals/run.py --mode reference-check --dataset data/generated/full --split heldout
python evals/run.py --mode api --base-url http://localhost:8000 --split heldout
```

The `reference-check` run verifies generated answer keys against the data. The `api` run measures the actual product through its HTTP interface. Fixture-only correctness must not be presented as model quality. Live CONNECTED evaluation requires a configured key, model, spending cap, and an explicit separate result report.

## Metrics and release targets

- Answerable held-out questions: exact/semantic correct results divided by answerable held-out cases. Target ≥90%.
- Ambiguous/unanswerable questions: appropriate clarification or abstention divided by such held-out cases. Target ≥90%.
- All 30 security cases: forbidden operations/cross-workspace requests must be denied. PostgreSQL read-only role must independently deny writes.
- Explicit invariants: delayed refund crossing month, duplicate refund rows, cancelled orders, zero denominators, join fan-out, and gross/net/discount reconciliation must all pass.
- On the full generated database, report actual p50/p95 SQL latency and end-to-end latency with sample sizes, plus timeout/cancellation and truncation behavior.

## Recorded outcomes

The full-data validator passed on Windows/Python 3.12.13 on 2026-09-28. The fixture-only reference check matched **63/63 answerable held-out keys** (`evals/results/fixture_reference_check.json`). The other 37 held-out cases are clarification/abstention or security scenarios and are outside this reference-key check. This confirms reference consistency only.

The final **DEMO API** run against the full PostgreSQL dataset and one worker scored **63/63 answerable results**, **15/15 clarification/abstention cases**, and **22/22 explicit security denials**, with no scored failures or transport errors. Its 100 requests were sent sequentially with a 500 ms pause between cases. End-to-end latency was p50 **1,101.71 ms**, p95 **2,173.73 ms** (`n=100`); SQL/query latency was p50 **726.11 ms**, p95 **1,416.85 ms** (`n=63` completed answer cases). Machine-readable per-case results and the readable report are [heldout_api_release.json](../evals/results/heldout_api_release.json) and [heldout_api_release.md](../evals/results/heldout_api_release.md). The historical first run and its 40 failures are retained in `evals/results/heldout_api_final.md`; they led to fixes for cancellation-only null groups, customer-subject parsing/cohort intent, and readable policy errors. The final run is a fresh, internally consistent rerun after those fixes.

These measurements exceed the stated numerical targets on the synthetic held-out set, but they do not establish accuracy on a customer's schema or vocabulary, live CONNECTED-model quality, or causal explanation quality. The main browser journeys and responsive views passed separately after the API evaluation; the browser import published one additional synthetic row after that measurement. Container startup and live-model verification remain separate gates in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).
