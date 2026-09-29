# Commercialization notes

## Buyer and offer

The likely buyer is an operations or sales leader at a small or midsize business with a defined PostgreSQL sales schema, recurring questions, and staff who need inspectable figures without writing SQL. The v1 offer is a customer-specific installation and metric-mapping service, followed by support for schema changes, model configuration, and evaluation. It is one customer per installation, not a public self-service SaaS product.

## Onboarding checklist

1. Agree on authorized data source, workspaces, roles, data retention, region, and network/HTTPS requirements.
2. Map the customer's order, line, refund, customer, product, channel, and campaign fields to the supported schema or the documented CSV template. Reconcile totals with the customer's finance owner.
3. Review every metric definition, especially refund recognition, cancelled orders, discounts, currency, UTC conversion, and returning-customer logic. Capture examples and counterexamples.
4. Provision PostgreSQL admin/app/analytical roles, rotate all example secrets, restrict network access, and enable backups and logging redaction.
5. Configure a supported model ID/key and spending cap if CONNECTED mode is wanted. Run a small live smoke test with approved data.
6. Run a customer-specific evaluation set, review errors with the owner, confirm access boundaries, and decide whether the measured quality supports rollout.

## Reusable modules

The semantic metric catalog, typed planner schema, bounded SQL policy, chart specification, synthetic scenario generator, CSV validation, report version renderer, and access tests are reusable. The analytical views, column mappings, prompts, customer vocabulary, roles, and deployment settings require customer-specific review.

## Cost model

DEMO needs no model API spend. CONNECTED cost depends on the configured model, number of model calls, token use, processing tier, and provider contract. Let `Q` be questions/month, `C` model calls/question, `I` average input tokens/call, `O` average output tokens/call, and `P_in`/`P_out` prices per million tokens. Estimated monthly model cost is `Q × C × (I × P_in + O × P_out) / 1,000,000`. For an illustrative workload of 10,000 questions, one planning call/question, 2,500 input and 300 output tokens/call, usage is 25 million input and 3 million output tokens; apply the selected model's actual current rates. Check the [official OpenAI API pricing page](https://developers.openai.com/api/docs/pricing) before quoting a customer. This is a planning formula, not measured usage or a guaranteed bill.

Database/storage cost is `provisioned GB × hosting rate` plus backups, logs, and data transfer. Size depends on imported rows, report retention, checkpoint retention, and indexes; measure a customer pilot before sizing. Local Compose uses the customer's own machine and has no managed hosting fee, but it still consumes disk, memory, and operational time. Set query and model budgets in the deployment config and watch actual token usage.

## Supported integrations and limits

V1 supports its bundled PostgreSQL sales schema, a documented sales CSV import, and a configured OpenAI model adapter through LangChain for typed planning. Model-written explanation of computed results is pending a separate data-egress review. Arbitrary database connections, arbitrary schemas, scheduled reports, forecasting, subscriptions, billing, and enterprise tenancy are outside v1. Live-model quality and customer-schema correctness require separate verification. Browser and database performance on the full generated profile are tracked in [EVALUATION.md](EVALUATION.md).

## Redistribution review

The project source and synthetic content are original for this portfolio build. Bundled dependency licenses and any web assets must be checked from their installed package metadata and distribution terms before shipping a commercial bundle. No third-party logo, testimonial, customer identity, or revenue claim is licensed or implied here. The dependency/license audit status is recorded in [DEPENDENCIES.md](DEPENDENCIES.md); an incomplete audit is a release gate.
