# Workspace upgrade — 2026-10-06

This document archives the first upgrade. The latest workbench layout, Dark/Light/System behavior and production-bundle browser instructions are in [WORKBENCH_THEMES.md](WORKBENCH_THEMES.md).

This pass improves the existing analytics product without replacing its query compiler, permissions, report model, or evaluation protocol. The API adds dataset classification metadata and permits the assigned local DEMO frontend origin. All bundled business data are synthetic. Historical benchmark figures in the other documents remain historical synthetic DEMO measurements; this UI pass does not establish model accuracy, customer outcomes, or new latency results.

## Product behavior

- The notebook explains the question → evidence → report workflow and shows source identity, dataset reference date and metric definitions before a question is run. Source identity comes from the catalog's additive `dataset_kind`, independently of DEMO/CONNECTED model mode. Seed-only, imported and mixed workspaces have distinct labels; missing/unknown sources remain unconfirmed. New seeds retain an explicit source marker, known historical bundled seed paths are recognized, and unmapped connector sources remain unknown. An old API without this new field uses the legacy synthetic flag as a compatibility fallback.
- The guided builder selects a catalog-backed metric, grouping, period and optional previous-period comparison. It puts a readable question into the composer for review. Exact bounds still come from the backend planner and appear in result evidence. Unsupported metrics, dimensions and periods are not silently offered.
- The three starter questions use supported DEMO grammar. The previous “last quarter” example was removed because the deterministic planner did not resolve that phrase to calendar-quarter bounds.
- Request failure restores the draft and offers retry. Its text acknowledges that a network failure cannot prove whether the server accepted the request. Notebook switching is disabled while the submission is in flight. Local results are scoped to the selected conversation.
- Result provenance uses the result's retained snapshot. A newer catalog reference is labeled separately; missing historical metadata is not replaced with current metadata.
- Dates explicitly display UTC, including offset-free UTC timestamps returned from SQLite. Client system timezone does not change the displayed evidence time.
- Charts omit missing/non-finite values instead of turning null into zero. The caption identifies the plotted subset of returned rows. Multiple series and unsupported chart types use the exact table. Empty queries provide a useful next step.
- Mobile navigation has focus trapping, Escape dismissal and an inert collapsed sidebar. Report dialogs restore focus. There is a skip link, keyboard submission, reduced-motion support and improved contrast/touch targets. This is targeted accessibility work, not a formal WCAG audit.

## Reusing the product for another client

Create `apps/web/.env.local` with public presentation settings only:

```dotenv
VITE_PRODUCT_NAME=DataTalk
VITE_WORKSPACE_NAME=Northstar Supply
VITE_DEMO_EMAIL=manager@northstar.example.com
```

Restart the dev server or rebuild after changing these settings. Vite exposes every `VITE_*` variable to the browser; do not put secrets there. These settings change presentation, not server authorization or workspace identity. `VITE_API_BASE` remains available for deployments; a same-origin `/api` proxy is preferred for cookie authentication.

Client presentation and starter questions live in `apps/web/src/workspace.ts`. The reusable builder is `features/notebook/QuestionBuilder.tsx`; catalog keys must be mapped to phrases the planner actually supports. Test any schema/metric adaptation with customer-owned questions. The visual layer is isolated in `src/workspace.css`, with accent, ink, border and radius tokens. Currency and UTC business conventions remain the existing API contract; changing them is a backend accounting change, not a branding edit.

## Local preview without Docker

Frontend uses port **4314** with `strictPort`; API/proxy target uses **8314**. No server is restarted automatically and no Docker daemon is required for the fixture preview.

For a functioning configured API, from the repository root:

```powershell
$env:PYTHONPATH = 'apps/api/src'
# Use your existing local database configuration; no credentials are supplied here.
./apps/api/.venv/Scripts/python.exe -m uvicorn datatalk.main:app --host 127.0.0.1 --port 8314
```

In a second terminal:

```powershell
Set-Location apps/web
node node_modules/vite/bin/vite.js --host 127.0.0.1
```

If the database is unavailable, use the explicitly **illustrative UI fixture API** instead:

```powershell
# Terminal 1, from apps/web:
node scripts/fixture-preview.mjs
# Terminal 2, from apps/web:
node node_modules/vite/bin/vite.js --host 127.0.0.1
```

Open <http://127.0.0.1:4314>. The fixture API binds only to loopback, uses `reviewer@fixture.example`, and stores disposable state in memory. Result narratives/SQL explicitly identify illustrative UI fixtures. It does not execute SQL or models. It supports analysis, clarification, denial, one-time request failure, empty results, report save/reopen and local login transitions. CSV imports, exports, version refresh, cancellation, SSE and actual authentication/security enforcement require the real API. Never use this fixture server as a production service.

In DEMO, the API accepts the assigned localhost/127.0.0.1 frontend origin on 4314; cross-site requests still fail. In CONNECTED, configure `DATATALK_ALLOWED_ORIGINS` explicitly for the chosen frontend origin as required by the existing policy. Use the existing dedicated worker when testing asynchronous jobs with the real API; the web preview alone does not run one.

## Reproducible checks

```powershell
# From apps/web (installed dependencies; Node 22.18+ recommended for TS stripping):
node --experimental-strip-types --test tests/*.test.ts
node scripts/check-openapi.mjs
node node_modules/typescript/bin/tsc --noEmit
# Production build:
node scripts/check-openapi.mjs
node node_modules/typescript/bin/tsc -b
node node_modules/vite/bin/vite.js build
node scripts/qa-workspace.mjs

# From repository root:
$env:PYTHONPATH = 'apps/api/src'
./apps/api/.venv/Scripts/python.exe -m pytest tests/api -p no:cacheprovider -q
./apps/api/.venv/Scripts/ruff.exe check --config apps/api/pyproject.toml apps/api/src tests/api --no-cache
```

The browser script uses an installed Chrome/Edge or `CHROME_PATH`. It downloads nothing and starts its own hidden headless process/profile, local fixture API and Vite server. Both ports must be free. It closes its owned processes after completion. Browser background traffic is disabled and an invalid proxy blocks non-loopback requests. The runner generates screenshots and `verification.json` under ignored `apps/web/node_modules/.datatalk-qa/`. This pass's selected screenshots and report are also copied to the durable `docs/screenshots/upgrade-2026-10-06/` folder; the original files are preserved. Archive new QA runs to a dated docs folder before reinstalling dependencies.

## Durable visual evidence

These screenshots use illustrative UI fixtures, not executed database or model results. The copies match the original QA files byte for byte.

All seven copies were verified with SHA-256 and are retained as repository evidence.

| Scene | Durable file |
| --- | --- |
| Desktop workspace, 1440px | [workspace-desktop.png](screenshots/upgrade-2026-10-06/workspace-desktop.png) |
| Mobile workspace, 390px | [workspace-mobile.png](screenshots/upgrade-2026-10-06/workspace-mobile.png) |
| Mobile guided builder | [builder-mobile.png](screenshots/upgrade-2026-10-06/builder-mobile.png) |
| Result table, original snapshot and UTC evidence | [result-desktop.png](screenshots/upgrade-2026-10-06/result-desktop.png) |
| Connection recovery state | [connection-desktop.png](screenshots/upgrade-2026-10-06/connection-desktop.png) |
| Mobile login | [login-mobile.png](screenshots/upgrade-2026-10-06/login-mobile.png) |
| Final fixture QA observations and exception record | [verification.json](screenshots/upgrade-2026-10-06/verification.json) |

## Verification record

- Seven frontend unit regressions passed: scoped question composition, unsupported scope refusal, data identity, historical provenance, workspace configuration, null/zero chart handling and UTC formatting.
- Six planner regressions passed against the existing deterministic planner, including period bounds, dimension and comparison. No database/model is used by these tests.
- Strict TypeScript and the regenerated 21-operation OpenAPI contract check passed. The contract check now requires the additive dataset classification fields.
- Ruff passed across `apps/api/src` and `tests/api` using the API's configuration. The two new Python test files and dataset classifier were also formatted. The web project has no ESLint configuration; strict TypeScript and JavaScript syntax checks are used rather than claiming an ESLint pass.
- The production frontend build passed with existing dependencies (OpenAPI check → TypeScript build → Vite). No install/download was needed.
- The complete API suite passed: **51 passed, 4 skipped** in 11.80 seconds. The four skips require `DATATALK_TEST_ANALYTICS_URL`: three PostgreSQL role checks and one PostgreSQL timeout check. New regressions cover guided question scope, dataset identity and the 4314 development origin without weakening cross-site denial.
- Isolated headless desktop (1440px) and mobile (390px, with a 320px overflow check) UI fixture regression passed for connection retry, initial states, builder, query/table, report save/reopen, clarification, policy denial, request retry, empty results, mobile focus/Tab/Escape, sign-out, failed login and successful retry. No uncaught browser exceptions were observed. Screenshots were visually inspected; the final source rerun is represented by the durable [verification.json](screenshots/upgrade-2026-10-06/verification.json).
- Existing dirty README, `.gitignore`, seven API/data test files and teaser assets were preserved. A whole-worktree `git diff --check` reports pre-existing CRLF/EOF issues in README/`.gitignore`; checks for this pass should be scoped to its changed paths.

## Remaining acceptance work

Verify against a real local PostgreSQL instance, asynchronous job/cancel/SSE behavior, imported customer data, report export/refresh/version comparisons, production hosting and the customer's devices. Docker startup was unavailable in this session. No paid model API, credentials, remote transmission, push, deployment or publication is part of this pass.

Existing `node_modules` contained 230 stale junctions to a renamed sibling checkout. They were retargeted only to the installed DataTalk `.pnpm` package store. Old junctions and a repair manifest remain under ignored `node_modules/.datatalk-link-backups/`; no package data or cache was deleted. This repair is local environment state, not a source-code dependency change.

## Changed source paths in this pass

All paths are relative to `datatalk/`. Existing user changes in README, `.gitignore`, the seven API/data test files and `teaser_assets/` are outside this change list and were preserved.

| Area | Paths |
| --- | --- |
| API metadata/origin | `apps/api/src/datatalk/dataset_identity.py`, `cli.py`, `main.py`, `schemas.py` |
| App/config/style | `apps/web/src/App.tsx`, `config.ts`, `workspace.ts`, `workspace.css`, `time.ts`, `ui.tsx`, `main.tsx` |
| Notebook/results | `apps/web/src/features/notebook/Notebook.tsx`, `QuestionBuilder.tsx`, `apps/web/src/features/analysis/AnalysisBlock.tsx`, `ResultVisual.tsx`, `chartData.ts` |
| Focus targets | `apps/web/src/features/reports/ReportsView.tsx`, `apps/web/src/features/imports/ImportsView.tsx` |
| Contract/tooling | `apps/web/src/api/client.ts`, `openapi.json`, `apps/web/package.json`, `vite.config.ts`, `scripts/check-openapi.mjs`, `scripts/fixture-preview.mjs`, `scripts/qa-workspace.mjs` |
| Regression tests | `apps/web/tests/workspace.test.ts`, `tests/api/test_guided_questions.py`, `tests/api/test_workspace_metadata.py` |
| Documentation | `docs/WORKSPACE_UPGRADE.md`, `API.md`, `HANDOVER.md`, `IMPLEMENTATION_STATUS.md`, `PORTFOLIO.md` |
| Durable evidence | `docs/screenshots/upgrade-2026-10-06/*.png`, `docs/screenshots/upgrade-2026-10-06/verification.json` |
