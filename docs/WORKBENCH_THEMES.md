# Analytics workbench and themes — 2026-10-07

DataTalk now presents a compact analytics tool: question editor, result records and a searchable data-context panel. The existing planner, query policy, permissions, report versions and import pipeline are retained. This follows the [October 6 upgrade](WORKSPACE_UPGRADE.md), whose screenshots and measurements remain an archive of that earlier interface.

## Product and interaction design

- The editor appears before results, with keyboard submission and a visible run state. Scope, dataset identity and the snapshot reference remain visible before submission. Starter questions are compact actions, and the catalog-backed guided builder remains available.
- A context panel searches metric names, keys and definitions plus dimensions. Expand a metric to inspect its definition and unit, or open the full catalog. At narrower widths the context panel follows the notebook, without shrinking the editor into an unusable column.
- Recent questions are a compact disclosure. Escape closes it and restores its summary focus. Choosing history closes the disclosure. Switching conversations remains blocked during submission.
- Chart, table, SQL, evidence and saved reports retain their separate roles. Chart points support pointer and keyboard inspection, a theme-aware value tooltip, Escape dismissal and a persistent exact-data table. Missing numbers remain distinct from zero, including negative values.
- Mobile retains the bottom navigation and the focus-trapped sidebar. Request recovery, clarification, policy denial, empty scope, connection failure, sign-in failure and report success retain explicit next actions.

## Theme contract and customization

The accessible native **Appearance** selector is present in the workspace, sign-in, initial connection and connection-error views. Choices are **Dark**, **Light**, and **System**. A fresh or invalid preference uses Dark. Valid existing choices are preserved in `localStorage` under `datatalk.theme`. If storage is blocked or full, switching still works in memory; persistence across reloads is unavailable in that situation. System follows OS changes live; explicit Light/Dark ignore OS changes. Valid cross-tab preferences synchronize through the storage event.

`public/theme-init.js` is a blocking, same-origin external script before the stylesheet and React entry in `index.html`. It resolves the preference and sets the root data attributes before paint, without an inline script or style exception. `public/theme-base.css` supplies semantic surface, text, border, status, focus, native `color-scheme`, code and chart tokens. It also defines the default dark surface before the application styles load. The theme-color browser metadata follows the resolved appearance. Hosts must serve both public files and allow same-origin scripts/styles; the production browser test uses `script-src 'self'; style-src 'self'` without `unsafe-inline`.

`ThemeControl.tsx` subscribes independently through `useSyncExternalStore`; theme changes do not change application keys or remount the notebook. Charts use CSS variables, so their palette, axes, grids and tooltip change without refreshing business data. The browser regression verifies editor DOM identity, draft text, context filter, modal fields, navigation state and a running request, and counts API calls around theme switches.

For a future client, change the public branding settings described in [WORKSPACE_UPGRADE.md](WORKSPACE_UPGRADE.md), starter wording in `src/workspace.ts`, and semantic palette in `public/theme-base.css`. Component layout is isolated in `src/workspace.css`; the older `styles.css` still supplies shared component plumbing. Match new builder mappings to the actual backend grammar. Appearance changes do not alter data, dates, currency, authentication, authorization, CSV or PDF output. No display-wide color inversion is applied.

## Reproduce the preview

From `apps/web`, use two terminals for the **illustrative UI fixture**, with no Docker or database:

```powershell
# Terminal 1
node scripts/fixture-preview.mjs
# Terminal 2
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4314 --strictPort
```

Open <http://127.0.0.1:4314>. The fixture API is on **8314**, binds only to loopback and stores disposable state in memory. Its result narrative and SQL state that values are synthetic UI fixtures and the SQL is not executed. For the real API, use the configured database/worker launch described in the previous handoff; use API port **8314**. No model key is needed for the fixture preview.

## Verification and evidence

Run frontend checks from `apps/web`, in this order:

```powershell
node scripts/check-openapi.mjs
node node_modules/typescript/bin/tsc -b
node --experimental-strip-types --test tests/*.test.ts
node node_modules/vite/bin/vite.js build
node scripts/qa-workspace.mjs
```

The browser runner requires installed Chrome/Edge or `CHROME_PATH`; it downloads nothing. It serves the actual `dist` bundle with a restrictive CSP, starts its own hidden headless browser/profile and fixture API, then closes the processes it owns. Both assigned ports must be free. It blocks non-loopback browser networking and does not use the shared interactive browser. Files are first produced under ignored `apps/web/node_modules/.datatalk-theme-qa/` and then archived in [screenshots/theme-2026-10-07](screenshots/theme-2026-10-07/). Build before QA because the runner intentionally does not build or serve source modules.

| Check | Result for this pass |
| --- | --- |
| OpenAPI request/response contract | 21 operations verified |
| Strict TypeScript and production bundle | Passed |
| Node unit regressions | 12 passed, including actual bootstrap behavior under OS/storage changes |
| API regression suite, isolated SQLite configuration | 51 passed; 4 PostgreSQL-dependent tests skipped |
| Ruff for API source and API tests | Passed |
| Headless production UI regression | Both themes, desktop 1440, intermediate 1024/768 and mobile 390; page overflow also checked at 320 |
| Browser theme behavior | Default/persisted pre-paint appearance, live System, blocked storage, native controls, unchanged work state and no theme-triggered business fetches |
| Functional UI flows | Builder/run/query/table/evidence, modal focus/save/reopen, catalog filter/empty, local CSV validation error, clarification, denial, request failure/draft retry, empty result, mobile navigation, sign-out and repeated sign-in |
| Browser runtime/CSP | No uncaught exceptions or CSP violations in the successful regression |
| Exact data/metadata contrast | At least 4.5:1 for rendered data cells, catalog summaries/counts, login note and tooltip surfaces in both themes |
| Visual review | Desktop workbench/chart, intermediate layouts, mobile editor/builder/table/navigation/login and error states in both themes |

No frontend ESLint configuration exists in this project; the reported frontend checks are strict TypeScript, Node syntax checks, contract, unit, build and browser checks. These accessibility changes have targeted keyboard/contrast/viewport inspection, not a formal WCAG certification.

The archive contains 34 PNG screenshots and `verification.json`, all copied byte-for-byte from the successful run. `sha256.json` records their hashes. Representative images are linked here:

| Scene | Dark | Light |
| --- | --- | --- |
| Desktop workbench, 1440 × 1050 | [Dark](screenshots/theme-2026-10-07/workspace-desktop-dark.png) | [Light](screenshots/theme-2026-10-07/workspace-desktop-light.png) |
| Chart with focused value tooltip | [Dark](screenshots/theme-2026-10-07/result-desktop-dark.png) | [Light](screenshots/theme-2026-10-07/result-desktop-light.png) |
| Mobile builder, 390 × 844 | [Dark](screenshots/theme-2026-10-07/builder-mobile-dark.png) | [Light](screenshots/theme-2026-10-07/builder-mobile-light.png) |
| Mobile exact table | [Dark](screenshots/theme-2026-10-07/result-mobile-dark.png) | [Light](screenshots/theme-2026-10-07/result-mobile-light.png) |
| Recoverable request failure | [Dark](screenshots/theme-2026-10-07/request-error-desktop-dark.png) | [Light](screenshots/theme-2026-10-07/request-error-desktop-light.png) |

The representative images and verification reports are committed repository evidence.

The fixtures verify interface behavior only. This pass does not establish database execution correctness beyond the API unit suite, live-model quality, performance improvement, customer adoption or production readiness. Docker startup, the four live PostgreSQL tests, connected-model execution, actual import publish, exports, report refresh/version comparison, SSE and cancellation still require the configured real API. Historical synthetic DEMO benchmarks were not rerun or used as claims for this redesign.

## Publication accessibility check

The initial desktop screenshot's Run action is **disabled**: the textarea value is empty and the visible question is only its placeholder; the inherited disabled opacity is `0.52`. This is confirmed in both themes by the browser's actual DOM state. The colors reported for that disabled control are the underlying CSS colors, without opacity compositing; the enabled contrast conclusions below use opacity `1`.

The focused check also found and fixed inherited background animation and a legacy hover background on primary actions. Background and foreground now use the same semantic accent pair atomically on a theme change; hover retains that pair. Disabled styling was retained. The runner now verifies an actual drafted question with an enabled Run action in normal, pointer-hover and focused states:

| Theme | Normal/focus | Hover, including brightness filter |
| --- | ---: | ---: |
| Dark | 9.55:1 | 10.69:1 |
| Light | 6.34:1 | 5.72:1 |

The mobile check explicitly verifies the menu and enabled Appearance selector fit inside the 54px header at a 390 × 844 viewport. At maximum scroll, the final context action ends at y=762.77 and fixed navigation begins at y=783, leaving 20.23px of clearance in both themes. The earlier broad mobile regression remains, and the full seven-flow regression passed again after the bounded CSS correction, with strict types/build, the 12 unit tests and OpenAPI contract rerun.

The new proof is archived separately, preserving earlier screenshot bytes: [publication-check.json](screenshots/publication-check-2026-10-07/publication-check.json), [enabled Dark](screenshots/publication-check-2026-10-07/run-enabled-desktop-dark.png), [enabled Light](screenshots/publication-check-2026-10-07/run-enabled-desktop-light.png), [mobile header](screenshots/publication-check-2026-10-07/mobile-header-light.png), [last mobile content](screenshots/publication-check-2026-10-07/mobile-last-content-dark.png). Both-theme variants and the rerun verification are in the same directory. This check changed only `src/workspace.css`, `scripts/qa-workspace.mjs` and this handoff/evidence.

## Changed paths in this theme pass

`apps/web/index.html`, `public/theme-init.js`, `public/theme-base.css`, `src/ThemeControl.tsx`, `src/App.tsx`, `src/workspace.css`, `features/notebook/Notebook.tsx`, `features/notebook/ContextPanel.tsx`, `features/analysis/ResultVisual.tsx`, `tests/theme.test.ts`, `scripts/fixture-preview.mjs`, `scripts/qa-workspace.mjs`, this document and the linked handoff/portfolio evidence. Earlier user changes and the previous upgrade remain uncommitted and preserved. No commit, push or deployment was made.
