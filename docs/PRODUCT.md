# Product definition

DataTalk serves a manager and analyst at one customer installation. It uses a defined sales schema for Northstar Supply and makes the evidence behind an answer inspectable. The primary workflow is question → interpretation or clarification → bounded SQL → result and chart → versioned report. The notebook should show business definitions, filters, freshness, row limits, source views, and SQL alongside each result.

## V1 capabilities

- Searchable semantic catalog with named metrics and dimensions.
- Conversational questions and follow-ups. An ambiguous request such as “best customers” must ask which metric and period to use before querying.
- One validated, read-only analytical query per attempt against allowlisted views. Query policy validates parsed SQL, scopes a workspace, caps rows, and times out expensive requests.
- Deterministically computed comparisons and chart choices with accessible table equivalents. “Why” answers identify observed changes and label causal uncertainty.
- Report library with immutable versions, CSV export, and a printable view. A refreshed report is a new version.
- CSV preview and transactional publish for the documented sales template, with rejected-row reporting.
- Separate DEMO and CONNECTED model adapters. The dataset is synthetic in both modes until customer data are imported.

## Business conventions

All stored money values are integer USD cents. Display rounds only after aggregation. Time is UTC and ranges are half-open: `start <= timestamp < end`. “Last month” means the previous complete UTC calendar month relative to the configured reference/current date. Cancelled orders contribute no completed-order sales. Gross sales are completed line quantity times unit price. Discounts are the per-line discounts on completed orders; the order discount column is their summary and must not be subtracted a second time. Refunds are recognized on their `refunded_at` date. Net revenue is gross sales minus discounts minus recognized refunds for the selected period. Completed orders count distinct completed order IDs. Average order value divides completed-order sales after discounts by completed orders, with a null result for zero orders. A returning customer has a completed order after an earlier completed order. See the running catalog for executable definitions and [EVALUATION.md](EVALUATION.md) for invariant checks.

## Demonstration script

Ask which channel's net revenue changed most last month. Inspect the returned chart, table, date filter, and SQL. Drill into a product; save and reopen the report; refresh to create a second version. Ask why a change occurred and inspect the observed evidence and uncertainty statement. Try a forbidden query and inspect the readable rejection.

The generated company, people, transactions, and campaign histories are fictional. No real-customer performance or model accuracy is claimed by the demo.
