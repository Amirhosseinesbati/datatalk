# ADR 0001 — Modular monolith

Status: accepted, 2026-09-28.

Use one FastAPI service, one React client, and PostgreSQL. The application has clear model, analytics, import, report, and HTTP modules. This keeps installation and transaction boundaries comprehensible for a customer pilot. A separate queue or microservice is warranted only after measured workload requires it. The cost is that background execution and independent scaling are limited in v1.
