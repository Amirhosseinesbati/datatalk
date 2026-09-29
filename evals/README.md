# DataTalk evaluation assets

These are synthetic Northstar Supply evaluation cases. `questions.jsonl` holds 140 prompts and split labels. `private/reference.jsonl` holds SQL, metric definitions, and reference rows derived from the structured CSV dataset. **Do not mount either file into the API container, expose them through retrieval, or pass them to the planning model.** The private scenario rules are also withheld from runtime.

Counts: 60 standard aggregations, 30 joins/cohort/refund/date cases, 20 ambiguous or unanswerable cases, and 30 access/SQL/resource attacks. There are 40 development and 100 held-out cases. Among held-out cases, 63 require numerical answers, 15 require clarification or abstention, and 22 require rejection.

Generate from the full synthetic dataset after any seed or reference-date change:

```sh
python scripts/seed_data.py --profile full
python scripts/validate_data.py data/generated/full
python scripts/generate_evals.py
```

Check the reference SQL against the generated data. This is a fixture check, **not an app or model score**:

```sh
python evals/run.py --mode reference-check --dataset data/generated/full --split heldout
```

Evaluate a running local API using the demo account. The environment variables are optional overrides for the documented demo credentials:

```sh
python evals/run.py --mode api --base-url http://localhost:8000 --split heldout --pace-ms 500
```

For saved application predictions, provide JSONL records with `case_id`, `status`, and either `rows` or `result.rows`. A completed row set must contain a dimension such as `label`, `month`, `channel`, `category`, or `product`, and the metric value. The runner compares result values and dimensions, not SQL text or row ordering. It allows one cent absolute and 0.1% relative tolerance for numeric answers; nulls and UTC month labels are normalized. The default output is `evals/results/latest.json` and a matching Markdown report. Use `--output` and `--report` to preserve named runs.

```sh
python evals/run.py --mode predictions --predictions path/to/app_outputs.jsonl --split heldout --output evals/results/heldout_api.json
```

The API runner processes one case at a time and pauses 250 ms by default between cases (`--pace-ms` controls this). The result JSON reports numerator/denominator for numerical correctness, clarification or abstention, security denial, category totals, individual failures, and measured query/end-to-end p50/p95 latency for API runs when available. The release targets are 90% correctness on the 63 held-out answerable cases and 90% appropriate clarification or abstention on the 15 held-out ambiguous/unanswerable cases. A fixture reference check cannot establish those targets. Human review is still needed for explanation quality and causal wording.

Use `--case-ids DT-006 DT-007` for a focused debugging run. Such a subset reports its own denominator and should not be described as the held-out release score.

The runner checks both output paths for write access before sending the first API question. If a completed run's final write still fails, `--mode api-existing` can recover the exact latest 100 conversations in creation order and score their persisted analyses without re-executing questions. It verifies each question at the expected case position. Recovery reports query latency from saved results but leaves client end-to-end latency unavailable.
