# Architecture

DataTalk is a modular monolith with one PostgreSQL database and two roles at runtime. The app role manages conversations, imports, and report versions. The analytical role can select only scoped analytical views and defaults to read-only transactions. Each installation is intended for one customer, while two seeded workspaces test isolation.

```mermaid
flowchart LR
  Browser[React analytical notebook] -->|same-origin /api| API[FastAPI]
  API --> Auth[Session and workspace authorization]
  Auth --> Jobs[Persisted analysis jobs]
  Jobs --> Worker[Leased API worker]
  Worker --> Graph[LangGraph analysis workflow]
  Graph --> Catalog[Metric and schema catalog]
  Graph --> Planner[Typed planner: demo fixture or LangChain model]
  Graph --> Policy[SQL AST and resource policy]
  Policy -->|read-only role + workspace GUC| Views[PostgreSQL analytical views]
  Views --> Tables[(Sales tables)]
  Graph --> Checkpoints[(PostgreSQL checkpoints)]
  Graph --> Executions[Persisted query executions]
  API --> Reports[Saved report/version repository]
  Reports --> Tables
  API --> Import[CSV preview and transactional publish]
  Import --> Tables
```

```mermaid
erDiagram
  WORKSPACE ||--o{ CUSTOMER : owns
  WORKSPACE ||--o{ PRODUCT : owns
  WORKSPACE ||--o{ CHANNEL : owns
  WORKSPACE ||--o{ CAMPAIGN : owns
  CUSTOMER ||--o{ ORDER : places
  CHANNEL ||--o{ ORDER : receives
  CAMPAIGN |o--o{ ORDER : influences
  ORDER ||--o{ ORDER_LINE : contains
  PRODUCT ||--o{ ORDER_LINE : sold_as
  ORDER_LINE ||--o{ REFUND : can_receive
  WORKSPACE ||--o{ ANALYSIS_CONVERSATION : contains
  ANALYSIS_CONVERSATION ||--o{ QUERY_EXECUTION : records
  QUERY_EXECUTION ||--|| ANALYSIS_JOB : scheduled_as
  WORKSPACE ||--o{ SAVED_REPORT : owns
  SAVED_REPORT ||--o{ REPORT_VERSION : retains
  WORKSPACE ||--o{ DATA_IMPORT : receives
```

## Analysis boundary

Natural language never becomes an unrestricted database operation. The planner produces a typed metric/dimension/date/filter request. Compilation uses known views and columns. The SQL parser checks the AST, identifiers, functions, statement count, limit, and complexity. Execution sets a workspace-specific PostgreSQL transaction setting, read-only transaction, statement timeout, and row cap. The database role has no write grants or direct base-table read grants. Application validation and database privileges are independent checks.

The answer derives numeric claims from result rows, not generated prose. Report versions retain the question, plan, SQL, result, chart, snapshot/hash, and model/prompt versions. Conversation metadata is stored independently of result rows. See [SECURITY.md](SECURITY.md) for trust boundaries and [OPERATIONS.md](OPERATIONS.md) for recovery and backup.

## Decision records

- [0001 — Modular monolith](adr/0001-modular-monolith.md)
- [0002 — Typed plan and bounded SQL](adr/0002-typed-plan-and-sql-policy.md)
- [0003 — Synthetic fast/full profiles](adr/0003-synthetic-profiles.md)
- [0004 — Versioned report evidence](adr/0004-versioned-reports.md)
