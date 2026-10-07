# HTTP API

The FastAPI OpenAPI document is `/api/openapi.json`; the interactive local reference is `/api/docs`. All application routes have the `/api` prefix. The web client uses a same-origin proxy and sends the session cookie with requests. JSON is UTF-8. Authentication is required except for `/api/health` and `/api/auth/login`.

The catalog includes `dataset_kind` (`synthetic`, `imported`, `mixed`, or `unknown`), derived from workspace-scoped retained source records. It is independent of DEMO/CONNECTED model mode. The compatibility `synthetic` flag is true only for a seed-only dataset. CSV imports are additive, so a seeded workspace with published imports is mixed; an unmapped source remains unknown. New seed snapshots carry a `synthetic-seed:` marker. The workspace UI retains each result's own snapshot metadata and displays UTC times. See [WORKSPACE_UPGRADE.md](WORKSPACE_UPGRADE.md) for the current 4314/8314 preview and verification record.

| Method and path | Purpose | Role |
| --- | --- | --- |
| `GET /api/health` | Database reachability and mode | Public |
| `POST /api/auth/login` | Start cookie session with `{email,password}` | Public |
| `POST /api/auth/logout` | Revoke current cookie session | Signed in |
| `GET /api/session` | Current user, role, workspace, mode | Signed in |
| `GET /api/catalog` | Metric/dimension definitions, date conventions, source tables, freshness | Signed in |
| `POST /api/conversations` | Create a notebook conversation | Signed in |
| `GET /api/conversations` | List workspace conversations, capped | Signed in |
| `GET /api/conversations/{id}` | Reopen one conversation and its analyses | Signed in |
| `POST /api/conversations/{id}/analyses` | Queue a question with `{question}` | Signed in |
| `GET /api/analyses/{id}` | Fetch status, plan, SQL, result, chart, evidence | Signed in |
| `GET /api/analyses/{id}/events` | Live SSE stage/done events | Signed in |
| `POST /api/analyses/{id}/cancel` | Request cancellation | Signed in |
| `POST /api/reports` | Save a completed analysis with `{analysis_id,title}` | Admin/operator |
| `GET /api/reports` | List workspace reports and versions | Signed in |
| `GET /api/reports/{id}` | Reopen a report | Signed in |
| `GET /api/reports/{id}/versions/{n}` | Reopen immutable version `n` | Signed in |
| `POST /api/reports/{id}/refresh` | Queue a new analysis/version | Admin/operator |
| `GET /api/reports/{id}/export.csv` | Export latest stored version | Signed in |
| `GET /api/reports/{id}/print` | Printable HTML for latest stored version | Signed in |
| `GET /api/imports/template.csv` | Download supported sales CSV header | Signed in |
| `POST /api/imports/preview` | Multipart upload, validate, stage accepted rows | Admin/operator |
| `POST /api/imports/publish` | Publish staged token transactionally | Admin/operator |
| `GET /api/imports` | List workspace import summaries | Signed in |

## Analysis lifecycle

`POST /api/conversations/{id}/analyses` accepts `{"question":"Which channel's net revenue changed most last month?"}` and returns HTTP 201 with a server-owned analysis ID and `queued` status. `GET /api/analyses/{id}` moves through queued/running stages to `completed`, `clarification`, `failed`, or `cancelled`. SSE sends `stage` events with observable stage names and a final `done`; the GET resource is authoritative after reconnect. The client can poll if SSE is unavailable. No endpoint accepts raw SQL from the browser.

A completed analysis includes `plan`, validated `sql`, bound parameter values except workspace ID, `result` (`columns`, `rows`, `row_count`, `truncated`, `row_cap`), `chart`, `narrative`, `evidence`, `events`, and the dataset `snapshot` ID/hash/reference date. Dates and timestamps use UTC; amounts are integer USD cents in the API. `clarification` returns a question to narrow ambiguity before any analytical SQL is run. Unsafe/unsupported requests do not return a successful result. The SQL shown to users contains named bound parameters rather than inlined filter values.

`POST /api/reports/{id}/refresh` returns the queued `analysis_id`; poll it, then refetch the report. A successful refresh appends a new version. A failed refresh keeps the prior version intact. Version response retains the exact result, plan, SQL, chart, snapshot identity, model/prompt version, and evidence stored when that version was created. CSV and print exports read a stored version, not a fresh query.

## CSV template

The template columns, in order, are `order_id,customer_id,customer_name,customer_email,ordered_at,channel,product_id,product_name,category,quantity,unit_price_cents,discount_cents,status,currency`. `ordered_at` must have a UTC offset; currency is USD; status is `completed` or `cancelled`. The preview response gives a token, accepted/rejected row counts, a small accepted preview, and row errors. Publish accepts `{"token":"..."}`. The upload limit is configurable (`DATATALK_IMPORT_MAX_BYTES`, default 2 MB). The server commits accepted rows and a dataset snapshot in one transaction. A repeat publish of the same token returns its published status without duplicating rows.

## Errors and access

HTTP 401 means no valid session, 403 means the signed-in role cannot perform the operation, 404 hides missing or other-workspace resources, 400/422 report validation or unsupported input, 413 reports an oversized CSV, and 503 means the database health check failed. Internal failures should be recorded by analysis ID without returning secrets. The API scope and report IDs are not authority by themselves; every lookup checks the current workspace. The browser must not store model or database credentials.
