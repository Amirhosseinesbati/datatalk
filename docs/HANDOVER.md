# Handover

## Latest local workbench/theme pass - 2026-10-07

The compact question/results/data-context workbench now supports persisted Dark, Light and live System appearance, with an external pre-paint bootstrap and semantic chart colors. Current evidence, customization, checks and limitations are in [WORKBENCH_THEMES.md](WORKBENCH_THEMES.md). Development ports remain **4314** (web) and **8314** (API); the headless runner now tests the built production bundle under CSP. No live model or container result is claimed for this pass.

## Previous local workspace pass - 2026-10-06

The guided analytics workspace, configurable branding, dataset identity, historical provenance, UTC times, responsive navigation and fixture browser regressions are documented in [WORKSPACE_UPGRADE.md](WORKSPACE_UPGRADE.md). Current development ports are **4314** (web) and **8314** (API). That document includes the Docker-free illustrative preview and separates UI fixture checks from actual database/model verification. The older verification matrix below records the September baseline.

Updated: 2026-09-28. DataTalk is an independent portfolio pilot for a fictional company. All bundled sales data are synthetic.

## Exact demo launch

With Docker Compose installed and its daemon running, from the repository root:

PowerShell:

```powershell
Copy-Item .env.example .env
# Edit the three database passwords and DATATALK_SECRET_KEY in .env.
docker compose --env-file .env up --build -d
```

POSIX shell:

```sh
cp .env.example .env
# Edit the three database passwords and DATATALK_SECRET_KEY in .env.
docker compose --env-file .env up --build -d
```

After `.env` is configured, the one launch command is `docker compose --env-file .env up --build -d`. Browse to the port in `DATATALK_WEB_PORT` (default <http://localhost:8080>); the API reference uses `DATATALK_API_PORT` (default <http://localhost:8000/api/docs>). The bootstrap generates/loads the fast synthetic profile. Inspect startup with `docker compose --env-file .env ps` and `docker compose --env-file .env logs bootstrap api api-worker web`.

## Demo accounts

Default password in `.env.example`: `DemoPass123!` (overridden by `DATATALK_DEMO_PASSWORD`). These users are seeded only in DEMO mode and must be changed/disabled before customer data.

| Email | Workspace | Role |
| --- | --- | --- |
| `manager@northstar.example.com` | Northstar | admin |
| `operator@northstar.example.com` | Northstar | operator |
| `viewer@northstar.example.com` | Northstar | viewer |
| `manager@eastwind.example.com` | Eastwind fixture | admin |

CONNECTED mode requires a configured model ID/key and a non-demo user created with the CLI; demo accounts cannot sign in there. Use `python -m datatalk.cli create-user --help` for the final credential-safe syntax.

## Implementation and verification matrix

| Capability | Implemented | Verified on this host | Remaining evidence |
| --- | --- | --- | --- |
| Reproducible fast/full synthetic data | Yes | Full validator and 9 data/evaluator tests passed | Customer data mapping |
| PostgreSQL schema, views, roles, migration | Yes | Local PostgreSQL 18 bootstrap/full load and separate-database backup/restore smoke passed | Container build/startup |
| Question → validated query → chart/table → follow-up | Yes | Browser main flow passed at 1440/1024/390 px; final DEMO held-out run 63/63 numeric answers | CONNECTED live model run |
| Report save/reopen/version/CSV/print | Yes | API smoke passed with version 2; browser refresh and side-by-side version comparison passed | Container deployment smoke |
| CSV preview/transactional publish | Yes | Browser review showed 1 accepted/5 rejected; publish committed 1 accepted row; backend HTTP tests passed | Customer CSV mapping |
| Cross-workspace and role access | Yes | API smoke got 404/403 respectively; 3/3 direct DB reader-role tests passed | Customer network isolation review |
| Held-out evaluation | Runner and 140 cases | Final DEMO API run: 63/63 numeric, 15/15 clarification, 22/22 security | Live CONNECTED/customer-data evaluation |
| Connected model adapter | Typed planning configured; explanation stays deterministic | No live key or budget supplied; no live call made | Live smoke, customer review, and data-egress approval for model-written explanation |
| Docker Compose launch | Configuration and exact images | Config validation and the initial API image build passed | Web build failed when the host C: drive filled and containerd returned I/O errors; startup unverified |
| Responsive browser QA/screenshots | UI implemented | Main flow, mobile navigation/table, report comparison, catalog, import, and denial inspected at 1440/1024/390 px; 8 screenshots saved | Customer-device acceptance |

Detailed commands, results, and failures are in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md). Docker Engine responded and built the first API image, but its storage failed before the web image could build; the container stack was not run. On this host, the ignored `.env` uses free ports 18083 (web) and 18002 (API), while the working local development preview is at <http://127.0.0.1:5175/> with API on port 8002. The project must not be labeled production-ready from these checks alone.

## Current commit

The folder was initialized as a local Git repository for this build. Record the final commit hash after all implementation, checks, and documentation changes are committed. No remote publication is implied.

## Next customer-specific steps

Review their schema/CSV mapping and metric definitions with a data owner, configure non-demo users and model budget, deploy behind HTTPS with rotated secrets, set retention and encrypted backups, verify restore, run a customer-owned evaluation set, and approve the measured quality/security limits before rollout. See [COMMERCIALIZATION.md](COMMERCIALIZATION.md) and [OPERATIONS.md](OPERATIONS.md).
