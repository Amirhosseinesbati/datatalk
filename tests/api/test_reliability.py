"""Focused reliability checks for bounded reads and durable analysis jobs."""

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import datatalk.analysis as analysis_module
import datatalk.executor as executor_module
import pytest
from datatalk.database import Base, make_engine
from datatalk.executor import QueryExecutor
from datatalk.main import cancel_analysis
from datatalk.models import (
    AnalysisConversation,
    AnalysisJob,
    DatasetSnapshot,
    QueryExecution,
    User,
    Workspace,
)
from datatalk.worker import LEASE_SECONDS, MAX_ATTEMPTS, claim_job
from sqlalchemy import create_engine, text, update
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session


@pytest.fixture
def job_db():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    workspace = Workspace(id="workspace-one", name="Fixture")
    user = User(
        id="user-one",
        workspace_id=workspace.id,
        email="reliability@example.com",
        password_hash="unused",
        role="operator",
    )
    db.add(workspace)
    db.flush()
    db.add(user)
    db.flush()
    snapshot = DatasetSnapshot(
        id="snapshot-one",
        workspace_id=workspace.id,
        reference_date="2026-03-01",
        content_hash="fixture-hash",
        source="fixture",
        row_count=0,
    )
    conversation = AnalysisConversation(
        id="conversation-one",
        workspace_id=workspace.id,
        user_id=user.id,
        title="Fixture",
    )
    db.add_all([snapshot, conversation])
    db.flush()
    record = QueryExecution(
        id="analysis-one",
        workspace_id=workspace.id,
        conversation_id=conversation.id,
        question="Show revenue by month",
        status="queued",
        stage="queued",
        snapshot_id=snapshot.id,
        events_json=[],
    )
    db.add(record)
    db.flush()
    job = AnalysisJob(
        id="job-one",
        analysis_id=record.id,
        workspace_id=workspace.id,
        status="queued",
        attempt_count=0,
        cancellation_requested=False,
    )
    db.add(job)
    db.commit()
    try:
        yield engine, db, user, record, job
    finally:
        db.close()
        engine.dispose()


def test_live_lease_prevents_reclaim_and_expiry_retries_only_to_limit(job_db):
    _, db, _, record, job = job_db

    first = claim_job(db)
    assert first is job
    assert job.status == record.status == "running"
    assert job.attempt_count == 1
    assert job.lease_expires_at is not None
    assert job.lease_expires_at.replace(tzinfo=None) > datetime.now(
        timezone.utc
    ).replace(tzinfo=None)

    assert claim_job(db) is None
    db.refresh(job)
    assert job.attempt_count == 1

    for expected_attempt in range(2, MAX_ATTEMPTS + 1):
        job.lease_expires_at = datetime.now(timezone.utc) - timedelta(
            seconds=LEASE_SECONDS
        )
        db.commit()
        assert claim_job(db) is job
        assert job.attempt_count == expected_attempt

    job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=LEASE_SECONDS)
    db.commit()
    assert claim_job(db) is None
    db.refresh(job)
    db.refresh(record)
    assert job.status == record.status == "failed"
    assert record.stage == "failed"
    assert job.attempt_count == MAX_ATTEMPTS
    assert "retry limit" in record.error


def test_cancel_queued_analysis_stops_it_before_claim(job_db):
    _, db, user, record, job = job_db

    response = cancel_analysis(record.id, db, user)

    assert response == {"id": record.id, "status": "cancelled"}
    assert job.cancellation_requested is True
    assert job.status == record.status == record.stage == "cancelled"
    assert claim_job(db) is None
    assert job.attempt_count == 0


def test_cancellation_between_graph_stages_discards_partial_result(job_db, monkeypatch):
    engine, db, _, record, job = job_db
    job.status = "running"
    job.attempt_count = 1
    db.commit()

    class CancellingGraph:
        def stream(self, _initial, **_kwargs):
            db.execute(
                update(AnalysisJob)
                .where(AnalysisJob.id == job.id)
                .values(cancellation_requested=True)
            )
            db.commit()
            yield {"plan": {"status": "completed", "result": {"rows": [{"value": 1}]}}}

    monkeypatch.setattr(analysis_module, "engine", engine)
    monkeypatch.setattr(analysis_module, "QueryExecutor", lambda: object())
    monkeypatch.setattr(
        analysis_module, "build_graph", lambda *_args, **_kwargs: CancellingGraph()
    )

    processed = analysis_module.process_analysis(db, record, job)

    assert processed.status == processed.stage == "cancelled"
    assert processed.result_json is None
    assert processed.events_json[-1]["stage"] == "cancelled"


def test_executor_sets_read_only_workspace_and_timeout_before_query(monkeypatch):
    class RecordingConnection:
        def __init__(self):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params=None):
            self.calls.append((str(statement), params))
            if str(statement).startswith("SELECT order_id FROM analytics_events"):
                raise OperationalError(
                    str(statement), params, Exception("statement timeout")
                )

    connection = RecordingConnection()
    fake_engine = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"), connect=lambda: connection
    )
    monkeypatch.setattr(
        executor_module,
        "get_settings",
        lambda: SimpleNamespace(datatalk_row_cap=10, datatalk_statement_timeout_ms=13),
    )
    sql = "SELECT order_id FROM analytics_events WHERE workspace_id = :workspace_id LIMIT 2"

    with pytest.raises(OperationalError, match="statement timeout"):
        QueryExecutor(fake_engine).execute(
            sql, {"workspace_id": "workspace-one"}, "workspace-one", 2
        )

    assert [statement for statement, _ in connection.calls] == [
        "SET TRANSACTION READ ONLY",
        "SELECT set_config('datatalk.workspace_id', :workspace_id, true)",
        "SELECT set_config('statement_timeout', :timeout, true)",
        sql,
    ]
    assert connection.calls[1][1] == {"workspace_id": "workspace-one"}
    assert connection.calls[2][1] == {"timeout": "13"}


def test_executor_reports_truncation_only_when_more_rows_exist(monkeypatch):
    engine = make_engine("sqlite://")
    monkeypatch.setattr(
        executor_module,
        "get_settings",
        lambda: SimpleNamespace(datatalk_row_cap=10, datatalk_statement_timeout_ms=13),
    )
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE analytics_events (workspace_id text NOT NULL, order_id text NOT NULL)"
            )
            connection.execute(
                text(
                    "INSERT INTO analytics_events (workspace_id, order_id) VALUES (:w, :o)"
                ),
                [
                    {"w": "workspace-one", "o": "order-1"},
                    {"w": "workspace-one", "o": "order-2"},
                    {"w": "workspace-one", "o": "order-3"},
                    {"w": "other-workspace", "o": "order-4"},
                ],
            )
        executor = QueryExecutor(engine)
        sql = (
            "SELECT order_id FROM analytics_events WHERE workspace_id = :workspace_id "
            "ORDER BY order_id LIMIT 4"
        )
        truncated = executor.execute(
            sql, {"workspace_id": "workspace-one"}, "workspace-one", 2
        )
        exact = executor.execute(
            sql.replace("LIMIT 4", "LIMIT 2"),
            {"workspace_id": "workspace-one"},
            "workspace-one",
            2,
        )

        assert truncated["rows"] == [{"order_id": "order-1"}, {"order_id": "order-2"}]
        assert truncated["row_count"] == truncated["row_cap"] == 2
        assert truncated["truncated"] is True
        assert exact["rows"] == truncated["rows"]
        assert exact["truncated"] is False
    finally:
        engine.dispose()


def test_postgres_enforces_short_statement_timeout_when_reader_is_available():
    url = os.environ.get("DATATALK_TEST_ANALYTICS_URL")
    if not url:
        pytest.skip("Set DATATALK_TEST_ANALYTICS_URL for the PostgreSQL timeout check")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(
                text("SELECT set_config('statement_timeout', :timeout, true)"),
                {"timeout": "10"},
            )
            with pytest.raises(DBAPIError) as error:
                connection.execute(text("SELECT pg_sleep(0.05)"))
            assert "statement timeout" in str(error.value).lower()
            connection.rollback()
    finally:
        engine.dispose()
