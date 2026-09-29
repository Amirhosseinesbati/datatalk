from sqlalchemy import text
from datatalk.database import engine

with engine.connect() as connection:
    for row in connection.execute(text("SELECT j.status, j.attempt_count, j.lease_expires_at, j.worker_id, e.id, e.stage, e.question FROM analysis_jobs j JOIN query_executions e ON e.id=j.analysis_id WHERE e.status NOT IN ('completed','clarification','failed','cancelled') ORDER BY j.created_at LIMIT 20")):
        print(row)
    if engine.dialect.name == "postgresql":
        for row in connection.execute(text("SELECT pid, state, wait_event_type, wait_event, left(query,150) FROM pg_stat_activity WHERE datname=current_database() AND state <> 'idle'")):
            print("PG", row)
