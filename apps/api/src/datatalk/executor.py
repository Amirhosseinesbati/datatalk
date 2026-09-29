"""Bounded execution through a separately privileged analytical connection."""
from datetime import date, datetime
from decimal import Decimal
from time import perf_counter
from sqlalchemy import text
from sqlalchemy.engine import Engine
from .config import get_settings
from .database import engine as app_engine, make_engine
from .sql_policy import validate_sql


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == int(value) else float(value)
    return value


class QueryExecutor:
    def __init__(self, analytics_engine: Engine | None = None):
        settings = get_settings()
        if analytics_engine is not None:
            self.engine = analytics_engine
        elif settings.analytics_database_url:
            self.engine = make_engine(settings.analytics_database_url)
        elif settings.is_postgres:
            raise RuntimeError("ANALYTICS_DATABASE_URL is required for PostgreSQL; the app role cannot serve analytical reads")
        else:
            self.engine = app_engine

    def execute(self, sql: str, params: dict, workspace_id: str, display_cap: int) -> dict:
        settings = get_settings()
        validate_sql(sql, dialect="postgres" if self.engine.dialect.name == "postgresql" else "sqlite", row_cap=settings.datatalk_row_cap + 1)
        if params.get("workspace_id") != workspace_id:
            raise ValueError("workspace parameter mismatch")
        started = perf_counter()
        with self.engine.connect() as connection:
            if self.engine.dialect.name == "postgresql":
                connection.execute(text("SET TRANSACTION READ ONLY"))
                connection.execute(text("SELECT set_config('datatalk.workspace_id', :workspace_id, true)"), {"workspace_id": workspace_id})
                connection.execute(text("SELECT set_config('statement_timeout', :timeout, true)"), {"timeout": str(settings.datatalk_statement_timeout_ms)})
            result = connection.execute(text(sql), params)
            columns = list(result.keys())
            rows = [{key: _json_value(value) for key, value in row._mapping.items()} for row in result.fetchmany(display_cap + 1)]
            connection.rollback()
        truncated = len(rows) > display_cap
        rows = rows[:display_cap]
        return {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": truncated, "row_cap": display_cap, "query_duration_ms": round((perf_counter() - started) * 1000, 2)}
