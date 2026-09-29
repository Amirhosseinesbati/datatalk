# Dependencies and reproducibility

Checked on 2026-09-28. Python dependencies are locked in `apps/api/uv.lock`; JavaScript dependencies are locked in `apps/web/pnpm-lock.yaml`. Container base images use exact version tags in `apps/api/Dockerfile`, `apps/web/Dockerfile`, and `compose.yaml`. Regenerate locks only after compatibility review and rerun the full checks.

| Component | Tested local version | Source of version |
| --- | --- | --- |
| Python | 3.12.13 | bundled Windows interpreter |
| uv | 0.11.28 | local tool / API image |
| PostgreSQL | 18 local test cluster | Windows PostgreSQL install |
| FastAPI | 0.141.1 | `uv.lock` / installed environment |
| SQLAlchemy | 2.1.1 | `uv.lock` / installed environment |
| SQLGlot | 29.0.1 | `uv.lock` / installed environment |
| LangChain | 1.4.2 | `uv.lock` / installed environment |
| LangGraph | 1.2.12 | `uv.lock` / installed environment |
| psycopg | 3.3.6 | `uv.lock` / installed environment |
| Node.js | 24.18.0 | local tool |
| pnpm | 11.19.0 | local tool |
| React | 19.2.0 | `pnpm-lock.yaml` |
| TypeScript | 5.9.2 | `pnpm-lock.yaml` |
| Vite | 7.1.7 | `pnpm-lock.yaml` |
| Tailwind CSS | 4.1.13 | `pnpm-lock.yaml` |
| TanStack Query | 5.90.2 | `pnpm-lock.yaml` |

The backend uses the current LangChain structured-output model API and LangGraph StateGraph/checkpointer APIs as described in the [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output), [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), and [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) documentation. The Docker Compose dependency health ordering follows the [Docker Compose startup order guide](https://docs.docker.com/compose/how-tos/startup-order/). These pages were checked on 2026-09-28.

## License review

Installed Python package metadata was inventoried with `apps/api/.venv/Scripts/python.exe scripts/license_audit.py` and saved in [dependency_licenses.json](dependency_licenses.json): 79 distributions, including transitive packages. Two entries lacked wheel license metadata: this project's own `datatalk-api` package, whose redistribution license has not yet been selected, and `tiktoken` 0.14.0. The [upstream tiktoken license](https://github.com/openai/tiktoken/blob/main/LICENSE) is MIT. `psycopg`, `psycopg-binary`, and `psycopg-pool` declare LGPL-3.0-only in installed metadata; review the corresponding notice and distribution obligations before shipping an installer.

The frontend's installed direct-dependency inventory is [dependency_licenses_web.json](../apps/web/dependency_licenses_web.json) (12 packages). React, React DOM, TanStack Query, Vite, Tailwind CSS, and the React/Vite tooling report MIT; `lucide-react` reports ISC; TypeScript reports Apache-2.0. `node apps/web/scripts/license-report.mjs --json` regenerates that report. The application uses system fonts and code-drawn charts/icons, not bundled customer artwork. Container base images and the full frontend transitive tree still need a redistribution review on the built artifacts. Retain required notices; this inventory does not grant rights to third-party packages.

## Verification limits

The local API environment and web build were tested. Docker Engine 28.5.1 built the initial API image and installed the locked Python dependencies, but the host C: drive filled during that attempt. The following web image build failed with containerd metadata I/O errors; Compose startup remains unverified. The Dockerfile and Compose configuration were then adjusted to keep uv's download cache out of the final API image and build its shared API/worker/bootstrap image once. PostgreSQL integration results are tracked in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).
