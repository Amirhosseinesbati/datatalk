"""HTTP composition root. All resource lookups include the authenticated workspace."""
import asyncio
import csv
import html
import io
import json
import logging
from time import perf_counter
from uuid import uuid4
from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from .analysis import analysis_json, latest_snapshot, queue_analysis
from .auth import create_login_session, current_user, public_user, require_role, revoke_login_session, verify_password
from .catalog import public_catalog
from .config import get_settings
from .database import SessionLocal, engine, get_session
from .imports import preview_import, publish_import, template_csv
from .logging_utils import configure_datatalk_logging
from .models import AnalysisConversation, AnalysisJob, DataImport, DatasetSnapshot, QueryExecution, ReportVersion, SavedReport, User
from .schemas import (
    AnalysisOut, AnalysisRequest, CatalogOut, ConversationListOut, ConversationOut,
    ConversationSummaryOut, ImportListOut, ImportPreviewOut, ImportPublishOut,
    ImportPublishRequest, LoginRequest, ReportListOut, ReportOut, ReportRefreshOut,
    ReportRequest, ReportVersionOut, SessionOut,
)

app = FastAPI(title="DataTalk API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
configure_datatalk_logging()
logger = logging.getLogger(__name__)


@app.middleware("http")
async def reject_cross_origin_writes(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site write request denied"}, status_code=403)
        origin = request.headers.get("origin")
        if origin:
            settings = get_settings()
            allowed = {str(request.base_url).rstrip("/")}
            allowed.update(value.strip().rstrip("/") for value in settings.datatalk_allowed_origins.split(",") if value.strip())
            if settings.datatalk_mode == "demo":
                allowed.update({"http://localhost:5173", "http://127.0.0.1:5173"})
            if origin.rstrip("/") not in allowed:
                return JSONResponse({"detail": "Request origin is not allowed"}, status_code=403)
    return await call_next(request)


@app.middleware("http")
async def record_request(request: Request, call_next):
    request_id = str(uuid4())
    started = perf_counter()
    details = {"request_id": request_id, "method": request.method, "path": request.url.path}
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error("request_failed", extra={**details, "error_type": type(exc).__name__})
        raise
    response.headers["X-Request-ID"] = request_id
    logger.info("request_completed", extra={**details, "status": response.status_code, "duration_ms": round((perf_counter() - started) * 1000, 2)})
    return response


def _conversation(db: Session, conversation_id: str, workspace_id: str) -> AnalysisConversation:
    item = db.get(AnalysisConversation, conversation_id)
    if not item or item.workspace_id != workspace_id:
        raise HTTPException(404, "Conversation not found")
    return item


def _analysis(db: Session, analysis_id: str, workspace_id: str) -> QueryExecution:
    item = db.get(QueryExecution, analysis_id)
    if not item or item.workspace_id != workspace_id:
        raise HTTPException(404, "Analysis not found")
    return item


def _report(db: Session, report_id: str, workspace_id: str) -> SavedReport:
    item = db.get(SavedReport, report_id)
    if not item or item.workspace_id != workspace_id:
        raise HTTPException(404, "Report not found")
    return item


def _snapshot_json(db: Session, record: QueryExecution) -> dict:
    snapshot = db.get(DatasetSnapshot, record.snapshot_id) if record.snapshot_id else None
    return {**analysis_json(record, snapshot), "model_version": get_settings().datatalk_model_id if get_settings().datatalk_mode == "connected" else "demo-grammar-v1", "prompt_version": "planning-v1", "source_tables": (record.evidence_json or {}).get("source_tables", [])}


def _version_json(version: ReportVersion) -> dict:
    return {**version.snapshot_json, "version": version.version, "version_created_at": version.created_at.isoformat(), "analysis_id": version.analysis_id}


def _report_json(db: Session, report: SavedReport) -> dict:
    versions = db.scalars(select(ReportVersion).where(ReportVersion.report_id == report.id, ReportVersion.workspace_id == report.workspace_id).order_by(ReportVersion.version.asc())).all()
    latest = versions[-1] if versions else None
    return {"id": report.id, "title": report.title, "created_at": report.created_at.isoformat(), "current_version": latest.version if latest else None, "versions": [{"version": v.version, "created_at": v.created_at.isoformat(), "analysis_id": v.analysis_id} for v in versions], "latest_version": _version_json(latest) if latest else None}


@app.get("/health")
@app.get("/api/health")
def health() -> dict:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "mode": get_settings().datatalk_mode}
    except Exception:
        raise HTTPException(503, "Database unavailable")


@app.get("/api/session", response_model=SessionOut)
def session(user: User = Depends(current_user)) -> dict:
    return {"user": public_user(user), "mode": get_settings().datatalk_mode}


@app.post("/api/auth/login", response_model=SessionOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_session)) -> dict:
    user = db.scalars(select(User).where(User.email == payload.email.lower().strip())).first()
    if not user or not verify_password(user.password_hash, payload.password):
        raise HTTPException(401, "Invalid email or password")
    if user.is_demo and get_settings().datatalk_mode != "demo":
        raise HTTPException(403, "Demo account is unavailable in connected mode")
    create_login_session(db, user, response)
    return {"user": public_user(user), "mode": get_settings().datatalk_mode}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_session)) -> dict:
    revoke_login_session(db, request, response)
    return {"ok": True}


@app.get("/api/catalog", response_model=CatalogOut)
def catalog(db: Session = Depends(get_session), user: User = Depends(current_user)) -> dict:
    snapshot = latest_snapshot(db, user.workspace_id)
    return {**public_catalog(), "freshness": {"snapshot_id": snapshot.id, "reference_date": snapshot.reference_date, "created_at": snapshot.created_at.isoformat(), "hash": snapshot.content_hash} if snapshot else None, "synthetic": get_settings().datatalk_mode == "demo"}


@app.post("/api/conversations", status_code=201, response_model=ConversationSummaryOut)
def create_conversation(db: Session = Depends(get_session), user: User = Depends(current_user)) -> dict:
    item = AnalysisConversation(id=str(uuid4()), workspace_id=user.workspace_id, user_id=user.id, title="New analysis")
    db.add(item)
    db.commit()
    return {"id": item.id, "title": item.title, "created_at": item.created_at.isoformat()}


@app.get("/api/conversations", response_model=ConversationListOut)
def list_conversations(db: Session = Depends(get_session), user: User = Depends(current_user)) -> dict:
    records = db.scalars(select(AnalysisConversation).where(AnalysisConversation.workspace_id == user.workspace_id).order_by(AnalysisConversation.created_at.desc()).limit(100)).all()
    return {"items": [{"id": item.id, "title": item.title, "created_at": item.created_at.isoformat()} for item in records]}


@app.get("/api/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: str, db: Session = Depends(get_session), user: User = Depends(current_user)) -> dict:
    item = _conversation(db, conversation_id, user.workspace_id)
    analyses = db.scalars(select(QueryExecution).where(QueryExecution.conversation_id == item.id, QueryExecution.workspace_id == user.workspace_id).order_by(QueryExecution.created_at.asc())).all()
    return {"id": item.id, "title": item.title, "created_at": item.created_at.isoformat(), "analyses": [analysis_json(a, db.get(DatasetSnapshot, a.snapshot_id) if a.snapshot_id else None) for a in analyses]}


@app.post("/api/conversations/{conversation_id}/analyses", status_code=201, response_model=AnalysisOut)
def create_analysis(conversation_id: str, payload: AnalysisRequest, db: Session = Depends(get_session), user: User = Depends(current_user)) -> dict:
    conversation = _conversation(db, conversation_id, user.workspace_id)
    try:
        record = queue_analysis(db, conversation, user, payload.question)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if conversation.title == "New analysis":
        conversation.title = payload.question[:100]
        db.commit()
    return analysis_json(record, db.get(DatasetSnapshot, record.snapshot_id) if record.snapshot_id else None)


@app.get("/api/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: str, db: Session = Depends(get_session), user: User = Depends(current_user)) -> dict:
    record = _analysis(db, analysis_id, user.workspace_id)
    return analysis_json(record, db.get(DatasetSnapshot, record.snapshot_id) if record.snapshot_id else None)


@app.get("/api/analyses/{analysis_id}/events")
def analysis_events(analysis_id: str, db: Session = Depends(get_session), user: User = Depends(current_user)):
    _analysis(db, analysis_id, user.workspace_id)
    workspace_id = user.workspace_id
    user_id = user.id
    async def events():
        seen = 0
        while True:
            with SessionLocal() as poll_db:
                live_user = poll_db.get(User, user_id)
                record = poll_db.get(QueryExecution, analysis_id)
                if not live_user or live_user.workspace_id != workspace_id or not record or record.workspace_id != workspace_id:
                    yield "event: error\ndata: {\"message\":\"Access revoked\"}\n\n"
                    break
                history = list(record.events_json or [])
                for event in history[seen:]:
                    yield f"event: stage\ndata: {json.dumps(event)}\n\n"
                seen = len(history)
                if record.status in {"completed", "clarification", "failed", "cancelled"}:
                    yield f"event: done\ndata: {json.dumps({'status': record.status, 'analysis_id': record.id})}\n\n"
                    break
            await asyncio.sleep(0.5)
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})


@app.post("/api/analyses/{analysis_id}/cancel")
def cancel_analysis(analysis_id: str, db: Session = Depends(get_session), user: User = Depends(current_user)) -> dict:
    record = _analysis(db, analysis_id, user.workspace_id)
    if record.status in {"completed", "clarification", "failed", "cancelled"}:
        return {"id": record.id, "status": record.status}
    job = db.scalars(select(AnalysisJob).where(AnalysisJob.analysis_id == record.id, AnalysisJob.workspace_id == user.workspace_id)).first()
    if not job:
        raise HTTPException(404, "Job not found")
    job.cancellation_requested = True
    if job.status == "queued":
        job.status = "cancelled"
        record.status = "cancelled"
        record.stage = "cancelled"
    else:
        record.status = "cancelling"
        record.stage = "cancelling"
    db.commit()
    return {"id": record.id, "status": record.status}


@app.post("/api/reports", status_code=201, response_model=ReportOut)
def create_report(payload: ReportRequest, db: Session = Depends(get_session), user: User = Depends(require_role("admin", "operator"))) -> dict:
    analysis = _analysis(db, payload.analysis_id, user.workspace_id)
    if analysis.status != "completed":
        raise HTTPException(400, "Only completed analyses can be saved")
    report = SavedReport(id=str(uuid4()), workspace_id=user.workspace_id, title=payload.title.strip(), created_by=user.id)
    db.add(report)
    db.flush()
    version = ReportVersion(id=str(uuid4()), report_id=report.id, workspace_id=user.workspace_id, version=1, analysis_id=analysis.id, snapshot_json=_snapshot_json(db, analysis))
    db.add(version)
    db.commit()
    return _report_json(db, report)


@app.get("/api/reports", response_model=ReportListOut)
def list_reports(db: Session = Depends(get_session), user: User = Depends(current_user)) -> dict:
    records = db.scalars(select(SavedReport).where(SavedReport.workspace_id == user.workspace_id).order_by(SavedReport.created_at.desc()).limit(100)).all()
    return {"items": [_report_json(db, item) for item in records]}


@app.get("/api/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: str, db: Session = Depends(get_session), user: User = Depends(current_user)) -> dict:
    return _report_json(db, _report(db, report_id, user.workspace_id))


@app.get("/api/reports/{report_id}/versions/{version}", response_model=ReportVersionOut)
def get_report_version(report_id: str, version: int, db: Session = Depends(get_session), user: User = Depends(current_user)) -> dict:
    _report(db, report_id, user.workspace_id)
    item = db.scalars(select(ReportVersion).where(ReportVersion.report_id == report_id, ReportVersion.workspace_id == user.workspace_id, ReportVersion.version == version)).first()
    if not item:
        raise HTTPException(404, "Version not found")
    return _version_json(item)


@app.post("/api/reports/{report_id}/refresh", response_model=ReportRefreshOut)
def refresh_report(report_id: str, db: Session = Depends(get_session), user: User = Depends(require_role("admin", "operator"))) -> dict:
    report = _report(db, report_id, user.workspace_id)
    latest = db.scalars(select(ReportVersion).where(ReportVersion.report_id == report.id, ReportVersion.workspace_id == user.workspace_id).order_by(ReportVersion.version.desc())).first()
    if not latest:
        raise HTTPException(400, "Report has no version")
    old_analysis = _analysis(db, latest.analysis_id, user.workspace_id)
    conversation = _conversation(db, old_analysis.conversation_id, user.workspace_id)
    fresh = queue_analysis(db, conversation, user, old_analysis.question, report_id=report.id)
    return {"report_id": report.id, "analysis_id": fresh.id, "status": "queued", "current_version": latest.version}


def _latest_version(db: Session, report_id: str, workspace_id: str) -> ReportVersion:
    _report(db, report_id, workspace_id)
    item = db.scalars(select(ReportVersion).where(ReportVersion.report_id == report_id, ReportVersion.workspace_id == workspace_id).order_by(ReportVersion.version.desc())).first()
    if not item:
        raise HTTPException(404, "Version not found")
    return item


def _csv_safe(value) -> str:
    text_value = "" if value is None else str(value)
    return "'" + text_value if text_value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text_value


@app.get("/api/reports/{report_id}/export.csv")
def export_report_csv(report_id: str, db: Session = Depends(get_session), user: User = Depends(current_user)):
    version = _latest_version(db, report_id, user.workspace_id)
    result = version.snapshot_json.get("result") or {"columns": [], "rows": []}
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(result["columns"])
    for row in result["rows"]:
        writer.writerow([_csv_safe(row.get(column)) for column in result["columns"]])
    return Response(output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="report-{report_id}-v{version.version}.csv"'})


@app.get("/api/reports/{report_id}/print", response_class=HTMLResponse)
def print_report(report_id: str, db: Session = Depends(get_session), user: User = Depends(current_user)):
    report = _report(db, report_id, user.workspace_id)
    version = _latest_version(db, report_id, user.workspace_id)
    body = version.snapshot_json
    result = body.get("result") or {"columns": [], "rows": []}
    headings = "".join(f"<th>{html.escape(str(c))}</th>" for c in result["columns"])
    rows = "".join("<tr>" + "".join(f"<td>{html.escape(str(row.get(c, '')))}</td>" for c in result["columns"]) + "</tr>" for row in result["rows"])
    doc = f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{html.escape(report.title)}</title><style>body{{font:16px system-ui;max-width:900px;margin:40px auto;color:#102b49}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:8px;text-align:left}}th{{background:#eee}}pre{{white-space:pre-wrap}}</style></head><body><h1>{html.escape(report.title)}</h1><p>Version {version.version} · {html.escape(body.get('question',''))}</p><p>{html.escape(body.get('narrative') or '')}</p><table><thead><tr>{headings}</tr></thead><tbody>{rows}</tbody></table><h2>SQL</h2><pre>{html.escape(body.get('sql') or '')}</pre><p>Snapshot hash: {html.escape(str((body.get('snapshot') or {}).get('hash','unknown')))}</p></body></html>"
    return HTMLResponse(doc)


@app.get("/api/imports/template.csv")
def get_import_template(user: User = Depends(current_user)):
    return Response(template_csv(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="datatalk-sales-template.csv"'})


@app.post("/api/imports/preview", response_model=ImportPreviewOut)
async def import_preview(file: UploadFile = File(...), db: Session = Depends(get_session), user: User = Depends(require_role("admin", "operator"))) -> dict:
    return await preview_import(db, user, file)


@app.post("/api/imports/publish", response_model=ImportPublishOut)
def import_publish(payload: ImportPublishRequest, db: Session = Depends(get_session), user: User = Depends(require_role("admin", "operator"))) -> dict:
    return publish_import(db, user, payload.token)


@app.get("/api/imports", response_model=ImportListOut)
def list_imports(db: Session = Depends(get_session), user: User = Depends(current_user)) -> dict:
    imports = db.scalars(select(DataImport).where(DataImport.workspace_id == user.workspace_id).order_by(DataImport.created_at.desc()).limit(100)).all()
    return {"items": [{"id": item.id, "filename": item.filename, "status": item.status, "accepted_count": item.accepted_count, "rejected_count": item.rejected_count, "created_at": item.created_at.isoformat()} for item in imports]}
