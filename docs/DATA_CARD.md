# Synthetic data card

**Dataset:** Synthetic demo dataset — Northstar Supply. Every company, person, email, transaction, and revenue figure is fictional. The generator is `scripts/seed_data.py`; no customer source data are bundled.

## Reproduction

```sh
python scripts/seed_data.py --profile fast --seed 4104 --reference-date 2026-09-28
python scripts/seed_data.py --profile full --seed 4104 --reference-date 2026-09-28
```

The default reference date is 2026-09-28. The activity window is `[2025-03-28T00:00:00Z, 2026-09-28T00:00:00Z)`, 18 months. `--output` overrides the destination. Generated CSVs and their SHA-256 manifest stay in `data/generated/{fast,full}` and are excluded from Git; regenerate them for acceptance checks.

| Entity | Fast, all workspaces | Full, all workspaces |
| --- | ---: | ---: |
| Workspaces | 2 | 2 |
| Customers | 312 | 5,012 |
| Products | 66 | 206 |
| Channels | 8 | 8 |
| Orders | 1,030 | 50,030 |
| Order lines | 2,460 | 120,060 |
| Refunds | 75 | 3,359 |
| Campaigns | 4 | 4 |
| Campaign events | 12 | 12 |
| Inventory events | 32 | 32 |

The full Northstar workspace alone has exactly 5,000 customers, 200 products, six channels, 50,000 orders, and 120,000 lines. The additional Eastwind workspace has 12 customers, six products, two channels, 30 orders, and 60 lines to test isolation. The full Northstar sample includes 47,680 completed and 2,320 cancelled orders, with 3,356 refund records. These counts are from the generated full manifest for seed 4104/reference date 2026-09-28; they change with a different seed or date.

## Generation and integrity

Product popularity has a long tail; date sampling applies weekday/weekend and seasonal weights. Campaign periods raise sampling weight, and orders in a campaign can carry the campaign ID. Products have bounded stockout intervals with paired inventory events, so those products are not selected in that interval. About 4.6% of Northstar orders are cancelled. Some completed lines receive partial or full refunds after a delay; refunds are tied to specific lines and dated separately from the order. Each order's discount summary equals its line discount sum; the summary is not an extra deduction. Monetary values are integer USD cents and timestamps are UTC. A manifest lists row counts and per-file hashes.

For the stated full seed, 10,311 of 50,000 Northstar orders occur on weekends, 4,746 are campaign-attributed, the top 10% of customers account for 61.67% of orders, and the top 10% of products account for 40.14% of lines. There are 16 stockout windows and 2,546 refunds crossing an order/refund month boundary. These measured generation outputs are in `data/generated/full/qa_report.json`; they are not real-business observations.

The generator uses fictional IDs and `example.com` addresses. It emits a second workspace with disjoint IDs. It maintains foreign-key references and prevents refunds above the refundable line amount. `tests/data` checks reconciliation and reproducibility; their actual command/result is recorded in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

## Evaluation isolation and limits

Hidden event rules and expected answers belong under `evals/`; the runtime catalog and prompts may see only ordinary schema/metric definitions and query results. The evaluation set has development and held-out questions, including ambiguous, unsafe, and resource-heavy requests. A fixed-seed synthetic scenario tests deterministic arithmetic and policy behavior, but it does not establish quality on a customer's schema, vocabulary, or real data. Template/entity/date splits and measured held-out results are documented in [EVALUATION.md](EVALUATION.md).
