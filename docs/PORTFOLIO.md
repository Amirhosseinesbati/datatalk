# DataTalk — independent portfolio project

## Case study

**Problem.** Sales managers often depend on an analyst for ordinary questions, while an opaque chatbot can return persuasive but unsupported numbers. DataTalk explores a narrower, inspectable path for a company with a defined PostgreSQL sales schema.

**Approach.** A manager asks a question in an analytical notebook. A typed planner resolves metric, date, grain, currency, filters, and comparison or asks for clarification. A compiler builds one bounded query over a semantic event view, an AST policy validates it, and a separate read-only role executes it under a workspace scope and timeout. The notebook presents a chart and exact table, assumptions, SQL, source and snapshot metadata, then stores immutable report versions. A deterministic synthetic Northstar Supply scenario enables repeatable local demonstration without customer data.

**Engineering decisions.** The sales/refund event ledger recognizes refunds on their own date, avoiding retroactive changes to earlier period net revenue. Amounts stay in integer cents until display. A dedicated analytical role, explicit SQL AST validation, and server-derived workspace scope provide layered controls. Two isolated workspaces and a delayed-refund fixture exercise boundary and accounting behavior. A leased worker persists stages for long analyses; its recovery restarts a read-only attempt after a crash.

**Measured work to date.** The full synthetic Northstar profile has exactly 50,000 orders, 120,000 lines, 5,000 customers, and 200 products. Full-data integrity validation and nine data/evaluator tests passed. A final serial DEMO API run on 100 held-out synthetic questions scored 63/63 numeric results, 15/15 clarification/abstention cases, and 22/22 explicit security denials. End-to-end p50/p95 latency was 1,101.71/2,173.73 ms (`n=100`); query p50/p95 was 726.11/1,416.85 ms (`n=63`). The fixture-only reference check separately matched 63/63 answer keys. These are synthetic DEMO measurements, not live-model or customer-data accuracy. Browser results are tracked in [EVALUATION.md](EVALUATION.md) and [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

**Limits.** This is a self-hostable pilot for one customer's reviewed schema, not a general SQL agent or public SaaS. Manual browser QA covered the main analysis and follow-up, SQL evidence, reports and version comparison, CSV import preview and publish, catalog search, error handling, and responsive views at configured 1440, 1024, and 390 pixel widths. Automated browser regression, connected-model quality, live costs, container startup, and customer data mapping still need verification before commercial use. A local PostgreSQL logical backup/restore smoke passed; container restore remains unverified.

## 60–90 second demo script

1. Show the Synthetic demo dataset label, metric glossary, and current snapshot date (10 seconds).
2. Ask “Which channel's net revenue changed most last month?” Show live stages, the comparison result, chart, and table (20 seconds).
3. Ask a product follow-up; open assumptions, SQL, workspace filter, row cap, and source view (15 seconds).
4. Save, reopen, and refresh the report to show version history and CSV/print exports (20 seconds).
5. Ask “Why did it change?” and point out the observed evidence and causal uncertainty. Ask for a forbidden write and show rejection (15 seconds).

## 3–5 minute technical walkthrough

1. Explain the Northstar event schema, gross/discount/refund timing, and the full generator manifest.
2. Trace the LangGraph stages from authorization/catalog to plan, SQL compilation, AST validation, read-only execution, result validation, and presentation.
3. Open the PostgreSQL roles and security-barrier event view; show that the analytical role cannot write to base tables.
4. Demonstrate a report version's stored plan, SQL, result, chart, snapshot hash, and model/prompt identifiers.
5. Run the delayed-refund and workspace-isolation tests, then review held-out evaluation counts, latency, failures, and pending live-model checks without conflating fixture and model scores.

## Content angles

- Why a typed metric plan and SQL AST policy are more inspectable than unrestricted natural-language-to-SQL.
- How a dated event ledger fixes refund timing and join fan-out in sales analytics.
- What a synthetic 50,000-order scenario can and cannot prove about an analytics assistant.

## Screenshots

These eight screenshots were captured during manual browser QA. The viewport was configured at 1440, 1024, or 390 pixels wide; the saved raster can be narrower where the browser includes a scrollbar.

| Scene | Viewport width | Saved raster | Screenshot |
| --- | ---: | ---: | --- |
| Notebook answer and comparison chart | 1440 px | 1425 × 891 px | [notebook-1440.jpg](../apps/web/screenshots/notebook-1440.jpg) |
| Responsive notebook | 1024 px | 1009 × 887 px | [notebook-1024.jpg](../apps/web/screenshots/notebook-1024.jpg) |
| Mobile notebook and result navigation | 390 px | 375 × 811 px | [notebook-390.jpg](../apps/web/screenshots/notebook-390.jpg) |
| Saved report version comparison | 1440 px | 1425 × 891 px | [report-compare-1440.jpg](../apps/web/screenshots/report-compare-1440.jpg) |
| CSV import preview and rejected rows | 1440 px | 1425 × 891 px | [import-review-1440.jpg](../apps/web/screenshots/import-review-1440.jpg) |
| Analysis evidence and generated SQL | 1440 px | 1425 × 891 px | [evidence-sql-1440.jpg](../apps/web/screenshots/evidence-sql-1440.jpg) |
| Security denial state | 1440 px | 1440 × 900 px | [security-error-1440.jpg](../apps/web/screenshots/security-error-1440.jpg) |
| Searchable metric catalog | 1440 px | 1425 × 891 px | [catalog-search-1440.jpg](../apps/web/screenshots/catalog-search-1440.jpg) |

## Resume bullet templates backed by current measurements

- Built an independent FastAPI/React sales analytics pilot with a typed metric catalog, bounded PostgreSQL query path, and versioned report model; generated a reproducible 50,000-order/120,000-line synthetic scenario.
- Implemented synthetic data reconciliation and evaluation fixtures; full-data validation passed and a 100-case synthetic DEMO API evaluation scored 63/63 numeric, 15/15 clarification, and 22/22 security cases, with p95 end-to-end latency of 2,173.73 ms.

Do not claim customer adoption, revenue impact, live-model accuracy, or production readiness from synthetic data.
