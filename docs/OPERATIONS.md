# Operations

## Start and configure

Use the PowerShell or POSIX quick start in [README.md](../README.md). After `.env` is configured, run `docker compose --env-file .env up --build -d`; check `docker compose --env-file .env ps` and `docker compose --env-file .env logs bootstrap api api-worker web` for startup errors. Web and API bind to localhost on `DATATALK_WEB_PORT` (default 8080) and `DATATALK_API_PORT` (default 8000). The one-shot bootstrap generates the fast synthetic dataset, creates schema/views/users, and loads data before the API starts. It must be idempotent for restarts; verify the bootstrap completion status before accepting a customer install.

`DATATALK_MODE=demo` uses deterministic local planning. For a connected model test, set `DATATALK_MODE=connected`, `DATATALK_MODEL_ID`, and `OPENAI_API_KEY` on the API service. Set a provider budget/usage limit before a live smoke test. Missing or failed provider credentials must surface as an error. A schema-specific customer installation also requires their approved CSV mapping, semantic catalog review, baseline data reconciliation, and authorization roles.

For a separate development web origin, set `DATATALK_ALLOWED_ORIGINS` to a comma-separated list of exact origins (scheme, host, and port), for example `http://localhost:5175`. The production web app is served through the same origin and does not need that override. Cross-site write requests remain denied.

`DATATALK_IMPORT_PREVIEW_TTL_HOURS` defaults to 24 (allowed range 1–720). A publish request after that window returns HTTP 410. The worker checks for expired unpublished previews at startup and hourly. `DATATALK_MODEL_INPUT_USD_PER_MILLION` and `DATATALK_MODEL_OUTPUT_USD_PER_MILLION` are optional operator-supplied USD rates. CONNECTED analyses store provider-reported token counts when available and show cost as known only when both rates and token counts are available; otherwise cost remains unknown. These are estimates from configured rates, not billing records.

## Data and report lifecycle

Run `python scripts/seed_data.py --profile full` from the repository root for full synthetic acceptance data. The generated CSVs and manifest are reproducible, not source-controlled. Import preview validates a sales template; publish commits accepted rows or fails atomically. Saved report versions retain their result and source snapshot identity. Refresh creates a new version; it does not overwrite evidence.

After a successful publish, the import record's staged rows and preview rows are cleared in the same transaction. An expired unpublished preview is marked `expired` and those rows are cleared. The record still retains its file name, content hash, counts, and up to 200 validation errors; published sales rows remain in the database. Preview expiration does not remove uploaded data already published. Avoid using validation error text for sensitive content, and set a separate policy for the retained import metadata and sales records.

The seed loader is restricted to DEMO and the reserved synthetic workspace IDs. Loading an already published manifest is a no-op, including after later CSV imports. Replacing a different demo seed requires an explicit `--reset-demo` flag and must be refused while imported rows would be lost. Never run a demo reset against a customer workspace.

## Backup and restore

Back up PostgreSQL before import, migration, or retention cleanup. A container-local logical backup can be made with:

```sh
docker compose --env-file .env exec -T db pg_dump -U datatalk_admin -Fc -f /tmp/datatalk.dump datatalk
docker compose --env-file .env cp db:/tmp/datatalk.dump ./datatalk.dump
```

Store the resulting file encrypted outside the deployment host. A restore smoke test should use a separate database, never overwrite the active database:

```sh
docker compose --env-file .env cp ./datatalk.dump db:/tmp/datatalk-restore.dump
docker compose --env-file .env exec -T db createdb -U datatalk_admin datatalk_restore_smoke
docker compose --env-file .env exec -T db pg_restore -U datatalk_admin -d datatalk_restore_smoke --no-owner /tmp/datatalk-restore.dump
```

Then inspect table counts, a saved report version, and LangGraph checkpoint rows before dropping the smoke database. A local PostgreSQL 18 logical backup/restore smoke passed on 2026-09-28 with the full synthetic dataset; the container commands above remain untested because Docker storage failed before the stack started. The exact counts are in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md). Include checkpoint tables in backup and retention verification.

## Failures and limits

Analysis jobs and observable stages are stored so failures can be inspected with a run/conversation ID. A worker claims jobs with a lease; after a crash and lease expiry, another attempt restarts the read-only analysis from a fresh checkpoint thread. It does not resume inside an interrupted SQL/model call. The bounded query/model timeouts are shorter than the lease, and retries are capped. Cancellation is checked between stages; an in-flight SQL statement may still run until its database timeout. Query timeouts and row truncation should be shown to the user. Do not silently replace a connected-model failure with a demo response. A report version can be reopened from its stored result even when the source data have since changed; if a snapshot is no longer retained, say so explicitly.

Set retention for published sales rows, import metadata/errors, report versions, analyses, LangGraph checkpoints, and backups before deployment. The 24-hour preview cleanup is the only automatic data-retention rule in v1; report versions, analysis questions/results/SQL, and checkpoints are not automatically deleted. Application request/job logs use an allowlist of correlation IDs, stage/status, duration, method/path, and error type; they do not intentionally include question text, SQL, result rows, or model output. Restrict access to logs and verify any infrastructure-level access logging separately. LangSmith tracing is optional and disabled by default. The local demo is a pilot; it does not include a durable distributed job queue or autoscaling. Record expected concurrent users and measured p50/p95 latency on the full dataset before a customer rollout.
