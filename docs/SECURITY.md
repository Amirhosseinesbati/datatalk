# Security model

## Trust boundaries

Question text, follow-ups, CSV cells, imported file names, and model output are untrusted. They may describe a desired analysis but may not change the semantic catalog, authorize another workspace, choose a database connection, or issue tool instructions. The server chooses the workspace from the authenticated session, not from a request-supplied ID. In CONNECTED planning, the model receives the question and catalog definitions, never connection strings or credentials. Model-written explanation of computed results is pending data-egress approval; the implemented explanation uses server-computed evidence.

The analytical path compiles a typed plan into SQL with fixed view/column names and bound user values. `sqlglot` parses the completed statement. The policy allows one bounded SELECT over an approved view and rejects unapproved identifiers, subqueries/joins, wildcard selection, multiple statements, DDL/DML, unsafe functions, and missing/oversized LIMIT. A PostgreSQL read-only transaction, statement timeout, and a role with SELECT grants on analytical views only provide an independent write barrier. Views use a workspace setting and security barrier. The API sets that setting inside each read transaction; authorization must occur before the query and again before a saved version is reopened or exported.

## Session and data controls

- Passwords are hashed with Argon2. Deployment must provide a random `DATATALK_SECRET_KEY` and change the demo password.
- Session cookies should be HttpOnly, SameSite, and Secure behind HTTPS (`DATATALK_COOKIE_SECURE=true`). Use a single HTTPS origin in customer deployments.
- Mutating API requests reject cross-site fetch metadata and reject an `Origin` outside the current origin or explicitly configured `DATATALK_ALLOWED_ORIGINS`. Keep that allowlist narrow; the separate Vite origin is only for local development.
- The browser receives no database URL, provider key, or privileged role credential. `.env` is ignored by Git; `.env.example` contains placeholders only.
- Two seeded workspaces test access boundaries. A workspace filter is applied to records, report versions, imports, analyses, and query execution.
- CSV uploads must match the supported template and size/type limits. Exports escape cells beginning with spreadsheet formula characters. Rendered user text must be escaped or sanitized.
- Unpublished CSV preview rows expire after 24 hours by default (`DATATALK_IMPORT_PREVIEW_TTL_HOURS`); the worker clears staged and preview JSON at startup and hourly, while publish clears them transactionally. Expired publish attempts also clear these rows and return HTTP 410. Import metadata and capped validation errors remain until an operator retention policy removes them.
- Application request/job logs use an explicit field allowlist and correlation IDs. Raw questions, generated SQL, result rows, and model text are not logged by those handlers. The database still stores analysis questions, SQL, results, saved versions, and LangGraph checkpoints; these need access controls and an operator-defined retention schedule.
- CONNECTED model usage is recorded in analysis evidence when the provider returns token counts. Cost stays `unknown` unless both token counts and operator-configured input/output rates are available; it is not an authoritative billing figure. DEMO has no provider call.
- No public internet URL fetching is part of v1. There are no payment or external messaging actions.

## Known deployment requirements

The Compose mapping binds web/API ports to localhost for the local demo. A commercial installation needs an HTTPS reverse proxy, a rotated secret/password set, restricted network access to PostgreSQL, a retention schedule for published data, import metadata, reports, analyses, checkpoints and backups, encrypted backups, monitoring, and customer-specific schema/metric review. Demo credentials must be disabled or changed before any customer data is loaded. Infrastructure logs and provider-side data retention require separate review.

The workspace setting in views is a defense for application-mediated reads. If an attacker obtains the analytical role's database credential and direct SQL access, custom PostgreSQL settings can be changed; the customer deployment must keep that role inside the private network and should use one customer per installation. This is not a claim of public multi-tenant SaaS isolation. Security fixtures and direct role-permission checks are recorded in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).
