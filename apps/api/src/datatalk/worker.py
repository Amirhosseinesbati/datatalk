"""Durable, lease-based single-operation worker. Read-only graph runs can be retried safely."""
import logging
import time
from datetime import datetime, timedelta, timezone
from time import monotonic
from uuid import uuid4
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from .analysis import analysis_json, process_analysis
from .config import get_settings
from .database import SessionLocal
from .imports import expire_import_previews
from .logging_utils import configure_datatalk_logging
from .models import AnalysisJob, DatasetSnapshot, QueryExecution, ReportVersion, SavedReport

logger = logging.getLogger(__name__)
WORKER_ID = str(uuid4())
LEASE_SECONDS = 60
MAX_ATTEMPTS = 3


def claim_job(db: Session) -> AnalysisJob | None:
    now = datetime.now(timezone.utc)
    candidate = db.scalars(
        select(AnalysisJob)
        .where(or_(AnalysisJob.status == "queued", and_(AnalysisJob.status == "running", AnalysisJob.lease_expires_at < now)))
        .order_by(AnalysisJob.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if not candidate:
        db.rollback()
        return None
    record = db.get(QueryExecution, candidate.analysis_id)
    if candidate.cancellation_requested:
        candidate.status = "cancelled"
        if record:
            record.status = "cancelled"
            record.stage = "cancelled"
        db.commit()
        return None
    if candidate.attempt_count >= MAX_ATTEMPTS:
        candidate.status = "failed"
        if record:
            record.status = "failed"
            record.stage = "failed"
            record.error = "Worker stopped before completion after the retry limit."
        db.commit()
        return None
    candidate.status = "running"
    candidate.worker_id = WORKER_ID
    candidate.attempt_count += 1
    candidate.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
    if record:
        record.status = "running"
        record.stage = "claimed"
    db.commit()
    logger.info("job_claimed", extra={"analysis_id": candidate.analysis_id, "job_id": candidate.id, "workspace_id": candidate.workspace_id})
    return candidate


def _make_report_version(db: Session, job: AnalysisJob, record: QueryExecution) -> None:
    if not job.report_id or record.status != "finalizing":
        return
    report = db.scalars(select(SavedReport).where(SavedReport.id == job.report_id, SavedReport.workspace_id == job.workspace_id).with_for_update()).first()
    if not report:
        return
    latest_number = db.scalars(select(ReportVersion.version).where(ReportVersion.report_id == report.id).order_by(ReportVersion.version.desc())).first() or 0
    snapshot = db.get(DatasetSnapshot, record.snapshot_id) if record.snapshot_id else None
    body = {**analysis_json(record, snapshot), "status": "completed", "stage": "complete", "model_version": get_settings().datatalk_model_id if get_settings().datatalk_mode == "connected" else "demo-grammar-v1", "prompt_version": "planning-v1", "source_tables": (record.evidence_json or {}).get("source_tables", [])}
    db.add(ReportVersion(id=str(uuid4()), report_id=report.id, workspace_id=job.workspace_id, version=latest_number + 1, analysis_id=record.id, snapshot_json=body))


def run_once() -> bool:
    with SessionLocal() as db:
        job = claim_job(db)
        if not job:
            return False
        record = db.get(QueryExecution, job.analysis_id)
        if not record or record.workspace_id != job.workspace_id:
            job.status = "failed"
            db.commit()
            return True
        try:
            processed = process_analysis(db, record, job)
            _make_report_version(db, job, processed)
            if processed.status == "finalizing":
                processed.status = "completed"
                processed.stage = "complete"
            job.status = processed.status
            job.lease_expires_at = None
            db.commit()
            logger.info("job_finished", extra={"analysis_id": job.analysis_id, "job_id": job.id, "workspace_id": job.workspace_id, "status": job.status})
        except Exception as exc:
            logger.error("worker_failed", extra={"analysis_id": job.analysis_id, "job_id": job.id, "workspace_id": job.workspace_id, "error_type": type(exc).__name__})
            db.rollback()
            # Keep the lease so another process can recover after expiry.
        return True


def main() -> None:
    configure_datatalk_logging()
    last_cleanup = 0.0
    while True:
        now = monotonic()
        if now - last_cleanup >= 3600:
            try:
                with SessionLocal() as db:
                    expired = expire_import_previews(db)
                if expired:
                    logger.info("import_previews_expired", extra={"count": expired})
            except Exception as exc:
                logger.error("import_preview_cleanup_failed", extra={"error_type": type(exc).__name__})
            last_cleanup = now
        if not run_once():
            time.sleep(0.5)


if __name__ == "__main__":
    main()
