import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import get_settings
from .database import engine
from .executor import QueryExecutor
from .graph import build_graph
from .models import AnalysisConversation, AnalysisJob, Campaign, Channel, Customer, DatasetSnapshot, Product, QueryExecution, User, Workspace
from .planner import ConnectedPlanner, DemoPlanner

logger = logging.getLogger(__name__)


def analysis_json(record: QueryExecution, snapshot: DatasetSnapshot | None = None) -> dict:
    return {
        "id": record.id, "conversation_id": record.conversation_id, "question": record.question,
        "status": record.status, "stage": record.stage, "clarification": record.clarification,
        "plan": record.plan_json, "sql": record.sql_text, "parameters": {k: v for k, v in (record.params_json or {}).items() if k != "workspace_id"},
        "result": record.result_json, "chart": record.chart_json, "narrative": record.narrative,
        "evidence": record.evidence_json, "error": record.error, "events": record.events_json or [],
        "snapshot": {"id": snapshot.id, "hash": snapshot.content_hash, "reference_date": snapshot.reference_date, "created_at": snapshot.created_at.isoformat()} if snapshot else None,
        "created_at": record.created_at.isoformat(),
    }


def latest_snapshot(db: Session, workspace_id: str) -> DatasetSnapshot | None:
    return db.scalars(select(DatasetSnapshot).where(DatasetSnapshot.workspace_id == workspace_id).order_by(DatasetSnapshot.created_at.desc(), DatasetSnapshot.id.desc())).first()


def _filter_values(db: Session, workspace_id: str, question: str) -> dict:
    # Only names actually present in the question enter graph/model context.
    lower_question = question.lower()
    products = db.scalars(select(Product.name).where(Product.workspace_id == workspace_id)).all()
    customers = db.scalars(select(Customer.name).where(Customer.workspace_id == workspace_id)).all()
    campaigns = db.scalars(select(Campaign).where(Campaign.workspace_id == workspace_id)).all()
    return {
        "channel": list(db.scalars(select(Channel.name).where(Channel.workspace_id == workspace_id)).all()),
        "category": list(db.scalars(select(Product.category).where(Product.workspace_id == workspace_id).distinct()).all()),
        "product": [name for name in products if name.lower() in lower_question][:20],
        "customer": [name for name in customers if name.lower() in lower_question][:20],
        "campaign": [campaign.name for campaign in campaigns],
        "campaign_windows": {campaign.name: [campaign.starts_at.isoformat(), campaign.ends_at.isoformat()] for campaign in campaigns},
        "foreign_workspace_names": [part for name in db.scalars(select(Workspace.name).where(Workspace.id != workspace_id)).all() for part in (name, name.split()[0])],
    }


def queue_analysis(db: Session, conversation: AnalysisConversation, user: User, question: str, report_id: str | None = None) -> QueryExecution:
    snapshot = latest_snapshot(db, user.workspace_id)
    if not snapshot:
        raise ValueError("No dataset is loaded for this workspace")
    record = QueryExecution(id=str(uuid4()), workspace_id=user.workspace_id, conversation_id=conversation.id, question=question, status="queued", stage="queued", events_json=[], snapshot_id=snapshot.id)
    db.add(record)
    db.flush()
    job = AnalysisJob(id=str(uuid4()), analysis_id=record.id, workspace_id=user.workspace_id, status="queued", attempt_count=0, cancellation_requested=False, report_id=report_id)
    db.add(job)
    db.commit()
    return record


class AnalysisCancelled(Exception):
    pass


def process_analysis(db: Session, record: QueryExecution, job: AnalysisJob) -> QueryExecution:
    settings = get_settings()
    snapshot = db.get(DatasetSnapshot, record.snapshot_id)
    if not snapshot:
        raise ValueError("No dataset is loaded for this workspace")
    record.status = "running"
    record.stage = "scope"
    db.commit()
    logger.info("analysis_started", extra={"analysis_id": record.id, "job_id": job.id, "workspace_id": record.workspace_id})
    previous = db.scalars(select(QueryExecution).where(QueryExecution.conversation_id == record.conversation_id, QueryExecution.workspace_id == record.workspace_id, QueryExecution.status == "completed", QueryExecution.id != record.id).order_by(QueryExecution.created_at.desc(), QueryExecution.id.desc())).first()
    planner = DemoPlanner() if settings.datatalk_mode == "demo" else ConnectedPlanner(settings.datatalk_model_id)
    dialect = "postgresql" if engine.dialect.name == "postgresql" else "sqlite"
    initial = {
        "question": record.question, "workspace_id": record.workspace_id, "reference_date": snapshot.reference_date,
        "previous_plan": previous.plan_json if previous else None,
        "values": _filter_values(db, record.workspace_id, record.question),
    }
    state: dict[str, Any] = dict(initial)
    events: list[dict] = []
    try:
        executor = QueryExecutor()
        if engine.dialect.name == "postgresql":
            from langgraph.checkpoint.postgres import PostgresSaver
            url = settings.database_url.replace("+psycopg", "")
            with PostgresSaver.from_conn_string(url) as saver:
                graph = build_graph(planner, executor, dialect, settings.datatalk_row_cap, checkpointer=saver)
                updates = graph.stream(initial, config={"configurable": {"thread_id": f"{record.id}:{job.attempt_count}"}, "recursion_limit": 20}, stream_mode="updates")
                for update in updates:
                    for stage, delta in update.items():
                        db.refresh(job)
                        if job.cancellation_requested:
                            raise AnalysisCancelled()
                        state.update(delta or {})
                        events.append({"stage": stage, "at": datetime.now(timezone.utc).isoformat()})
                        record.stage = stage
                        record.events_json = list(events)
                        job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=60)
                        db.commit()
        else:
            graph = build_graph(planner, executor, dialect, settings.datatalk_row_cap)
            for update in graph.stream(initial, config={"recursion_limit": 20}, stream_mode="updates"):
                for stage, delta in update.items():
                    db.refresh(job)
                    if job.cancellation_requested:
                        raise AnalysisCancelled()
                    state.update(delta or {})
                    events.append({"stage": stage, "at": datetime.now(timezone.utc).isoformat()})
                    record.stage = stage
                    record.events_json = list(events)
                    job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=60)
                    db.commit()
        record.status = state.get("status", "failed")
        record.plan_json = state.get("plan")
        record.clarification = state.get("clarification")
        record.sql_text = state.get("sql")
        record.params_json = state.get("params")
        record.result_json = state.get("result")
        record.chart_json = state.get("chart")
        record.narrative = state.get("narrative")
        record.error = state.get("error")
        model_usage = state.get("model_usage")
        if not isinstance(model_usage, dict):
            model_usage = {"input_tokens": 0 if settings.datatalk_mode == "demo" else None, "output_tokens": 0 if settings.datatalk_mode == "demo" else None, "total_tokens": 0 if settings.datatalk_mode == "demo" else None, "cost_usd": 0.0 if settings.datatalk_mode == "demo" else None, "cost_status": "not_applicable" if settings.datatalk_mode == "demo" else "unknown"}
        record.evidence_json = {**(state.get("evidence") or {}), "source_view": state.get("source_view"), "source_tables": state.get("source_tables"), "metric_definitions": state.get("plan", {}).get("metrics", []) if state.get("plan") else [], "model_usage": model_usage}
        if record.status == "completed" and job.report_id:
            record.status = "finalizing"
            record.stage = "finalizing"
            events.append({"stage": "finalizing", "at": datetime.now(timezone.utc).isoformat()})
            record.events_json = events
        else:
            record.stage = "complete" if record.status == "completed" else record.status
    except AnalysisCancelled:
        record.status = "cancelled"
        record.stage = "cancelled"
        events.append({"stage": "cancelled", "at": datetime.now(timezone.utc).isoformat()})
        record.events_json = events
    except Exception as exc:
        logger.error("analysis_failed", extra={"analysis_id": record.id, "job_id": job.id, "workspace_id": record.workspace_id, "error_type": type(exc).__name__})
        record.status = "failed"
        record.stage = "failed"
        record.error = "Analysis could not be completed. Check the question, data and service configuration."
        events.append({"stage": "failed", "at": datetime.now(timezone.utc).isoformat()})
        record.events_json = events
    db.commit()
    db.refresh(record)
    logger.info("analysis_finished", extra={"analysis_id": record.id, "job_id": job.id, "workspace_id": record.workspace_id, "status": record.status})
    return record
