# Evaluation result status

- `fixture_reference_check.json` and `.md`: 63/63 held-out numerical references re-executed against the synthetic CSVs. This checks fixture consistency only; it does not measure application or model accuracy.
- `api_smoke.json` and `.md`: preliminary two-case API probe from before the date-parser and worker fixes. Both cases failed; this is retained as a debugging record and is not the release score.
- `fixture_smoke.json` and `.md`: three-case local reference probe, also fixture-only.
- `heldout_api_final.json` and `.md`: first full 100-case API run, recovered from persisted analyses after the result writer was denied. It measured 45/63 numerical answers, 15/15 clarification/abstention, and 0/22 **explicit** security rejections. The 22 security analyses returned `failed` with no rows but no readable denial message; they do not count as explicit policy rejections. Query p50/p95 are available for 59 saved executions; client end-to-end timings from the initial process were lost.
- `api_probe_remediation.json` and `.md`: seven focused cases after fixes, 7/7 passed. This is a diagnostic subset, not the release score.
- `heldout_api_release.json` and `.md`: final serial run on the corrected API, **100/100 held-out cases passed**. Numerical correctness 63/63, clarification/abstention 15/15, explicit security denial 22/22. Query p50/p95 726.11/1416.85 ms (n=63); end-to-end p50/p95 1101.71/2173.73 ms (n=100). No transport errors.

The final result is measured on a fixed synthetic dataset and should not be presented as real-customer accuracy. The 100-case split contains 63 answerable, 15 clarification/abstention, and 22 security-denial cases.
