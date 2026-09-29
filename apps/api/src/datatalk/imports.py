"""Validated CSV preview followed by one transactional publish."""
import csv
import hashlib
import io
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from uuid import uuid4
from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session
from .config import get_settings
from .models import Channel, Customer, DataImport, DatasetSnapshot, Order, OrderLine, Product, User

TEMPLATE_COLUMNS = ["order_id", "customer_id", "customer_name", "customer_email", "ordered_at", "channel", "product_id", "product_name", "category", "quantity", "unit_price_cents", "discount_cents", "status", "currency"]


def template_csv() -> str:
    return ",".join(TEMPLATE_COLUMNS) + "\n"


def _is_expired(created_at: datetime, now: datetime) -> bool:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at + timedelta(hours=get_settings().datatalk_import_preview_ttl_hours) <= now


def expire_import_previews(db: Session, now: datetime | None = None) -> int:
    """Discard raw staged rows after the configured preview retention window."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=get_settings().datatalk_import_preview_ttl_hours)
    result = cast(CursorResult[Any], db.execute(
        update(DataImport)
        .where(DataImport.status == "preview", DataImport.created_at <= cutoff)
        .values(status="expired", staged_json=[], preview_json=[])
    ))
    db.commit()
    return result.rowcount or 0


async def preview_import(db: Session, user: User, file: UploadFile) -> dict:
    settings = get_settings()
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Upload a .csv sales template")
    payload = await file.read(settings.datatalk_import_max_bytes + 1)
    if len(payload) > settings.datatalk_import_max_bytes:
        raise HTTPException(413, "CSV exceeds the configured upload limit")
    try:
        decoded = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "CSV must be UTF-8 encoded") from exc
    reader = csv.DictReader(io.StringIO(decoded))
    if reader.fieldnames != TEMPLATE_COLUMNS:
        raise HTTPException(400, f"CSV columns must be: {', '.join(TEMPLATE_COLUMNS)}")
    accepted: list[dict] = []
    errors: list[dict] = []
    order_signatures: dict[str, tuple] = {}
    customer_signatures: dict[str, tuple] = {}
    product_signatures: dict[str, tuple] = {}
    identity_orders: dict[str, set[str]] = {}
    inconsistent_identities: set[str] = set()
    rejected_orders: set[str] = set()
    for row_number, row in enumerate(reader, start=2):
        try:
            if any(value is None for value in row.values()):
                raise ValueError("wrong number of columns")
            for key in ("order_id", "customer_id", "customer_name", "channel", "product_id", "product_name", "category"):
                if not row[key].strip() or len(row[key]) > 180:
                    raise ValueError(f"{key} is required and must be <=180 characters")
            if row["customer_email"] and ("@" not in row["customer_email"] or len(row["customer_email"]) > 254):
                raise ValueError("customer_email is invalid")
            ordered_at = datetime.fromisoformat(row["ordered_at"].replace("Z", "+00:00"))
            if ordered_at.tzinfo is None or ordered_at.utcoffset() != timezone.utc.utcoffset(ordered_at):
                raise ValueError("ordered_at must include UTC offset")
            if row["status"] not in {"completed", "cancelled"}:
                raise ValueError("status must be completed or cancelled")
            if row["currency"] != "USD":
                raise ValueError("currency must be USD")
            quantity = int(row["quantity"])
            unit_price = int(row["unit_price_cents"])
            discount = int(row["discount_cents"])
            if quantity <= 0 or quantity > 10000 or unit_price < 0 or discount < 0 or discount > quantity * unit_price:
                raise ValueError("quantity, unit price or discount is out of range")
            signature = (row["customer_id"], row["customer_name"], row["customer_email"], row["ordered_at"], row["channel"], row["status"], row["currency"])
            if row["order_id"] in order_signatures and order_signatures[row["order_id"]] != signature:
                rejected_orders.add(row["order_id"])
                raise ValueError("rows for the same order have inconsistent order fields")
            order_signatures[row["order_id"]] = signature
            for identity_key, details, signatures in (
                ("customer_id", (row["customer_name"], row["customer_email"]), customer_signatures),
                ("product_id", (row["product_name"], row["category"]), product_signatures),
            ):
                identity = row[identity_key]
                identity_token = f"{identity_key}:{identity}"
                identity_orders.setdefault(identity_token, set()).add(row["order_id"])
                if identity_token in inconsistent_identities or (identity in signatures and signatures[identity] != details):
                    inconsistent_identities.add(identity_token)
                    rejected_orders.update(identity_orders[identity_token])
                    raise ValueError(f"{identity_key} has inconsistent details")
                signatures[identity] = details
            accepted.append({**row, "quantity": quantity, "unit_price_cents": unit_price, "discount_cents": discount, "row_number": row_number})
        except (ValueError, OverflowError) as exc:
            errors.append({"row": row_number, "message": str(exc)})
            if row.get("order_id"):
                rejected_orders.add(row["order_id"])
    if rejected_orders:
        for identity_token in inconsistent_identities:
            rejected_orders.update(identity_orders[identity_token])
        kept = []
        for row in accepted:
            if row["order_id"] in rejected_orders:
                errors.append({"row": row["row_number"], "message": "another row of this order was rejected"})
            else:
                kept.append(row)
        accepted = kept
    token = str(uuid4())
    record = DataImport(id=token, workspace_id=user.workspace_id, user_id=user.id, status="preview", filename=file.filename, content_hash=hashlib.sha256(payload).hexdigest(), accepted_count=len(accepted), rejected_count=len(errors), errors_json=errors[:200], preview_json=accepted[:10], staged_json=accepted)
    db.add(record)
    db.commit()
    return {"token": token, "accepted_count": record.accepted_count, "rejected_count": record.rejected_count, "errors": record.errors_json, "preview": record.preview_json}


def publish_import(db: Session, user: User, token: str) -> dict:
    record = db.get(DataImport, token)
    if not record or record.workspace_id != user.workspace_id:
        raise HTTPException(404, "Import not found")
    if record.status == "published":
        snapshot = db.scalars(select(DatasetSnapshot).where(DatasetSnapshot.workspace_id == user.workspace_id, DatasetSnapshot.source == f"csv-import:{record.id}")).first()
        return {"id": record.id, "status": record.status, "accepted_count": record.accepted_count, "rejected_count": record.rejected_count, "snapshot_id": snapshot.id if snapshot else None}
    if record.status == "expired":
        raise HTTPException(410, "Import preview expired; upload the CSV again")
    if record.status == "preview" and _is_expired(record.created_at, datetime.now(timezone.utc)):
        record.status = "expired"
        record.staged_json = []
        record.preview_json = []
        db.commit()
        raise HTTPException(410, "Import preview expired; upload the CSV again")
    if record.status != "preview" or record.accepted_count == 0:
        raise HTTPException(400, "Import has no valid rows to publish")
    prefix = "imp-" + token[:8] + "-"
    def scoped_id(kind: str, source: str) -> str:
        return prefix + kind + "-" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:32]
    orders: dict[str, Order] = {}
    customers: dict[str, Customer] = {}
    products: dict[str, Product] = {}
    channels: dict[str, Channel] = {}
    for index, row in enumerate(record.staged_json):
        cid = scoped_id("c", row["customer_id"])
        pid = scoped_id("p", row["product_id"])
        oid = scoped_id("o", row["order_id"])
        channel_name = row["channel"]
        if cid not in customers:
            customers[cid] = Customer(id=cid, workspace_id=user.workspace_id, name=row["customer_name"], email=row["customer_email"] or None, created_at=datetime.fromisoformat(row["ordered_at"].replace("Z", "+00:00")))
        if pid not in products:
            products[pid] = Product(id=pid, workspace_id=user.workspace_id, name=row["product_name"], category=row["category"], cost_cents=0)
        if channel_name not in channels:
            existing = db.scalars(select(Channel).where(Channel.workspace_id == user.workspace_id, Channel.name == channel_name)).first()
            channels[channel_name] = existing or Channel(id=scoped_id("ch", channel_name), workspace_id=user.workspace_id, name=channel_name)
        if oid not in orders:
            orders[oid] = Order(id=oid, workspace_id=user.workspace_id, customer_id=cid, channel_id=channels[channel_name].id, campaign_id=None, ordered_at=datetime.fromisoformat(row["ordered_at"].replace("Z", "+00:00")), status=row["status"], currency="USD", discount_cents=0)
        orders[oid].discount_cents += row["discount_cents"]
    try:
        db.add_all(customers.values())
        db.add_all(products.values())
        db.add_all(c for c in channels.values() if c.id.startswith(prefix))
        db.flush()
        db.add_all(orders.values())
        db.flush()
        for index, row in enumerate(record.staged_json):
            db.add(OrderLine(id=scoped_id("line", str(index)), workspace_id=user.workspace_id, order_id=scoped_id("o", row["order_id"]), product_id=scoped_id("p", row["product_id"]), quantity=row["quantity"], unit_price_cents=row["unit_price_cents"], discount_cents=row["discount_cents"]))
        imported_reference_date = max(datetime.fromisoformat(r["ordered_at"].replace("Z", "+00:00")).date().isoformat() for r in record.staged_json)
        previous_reference_date = db.scalar(select(func.max(DatasetSnapshot.reference_date)).where(DatasetSnapshot.workspace_id == user.workspace_id))
        snapshot = DatasetSnapshot(id=str(uuid4()), workspace_id=user.workspace_id, reference_date=max(imported_reference_date, previous_reference_date or imported_reference_date), content_hash=record.content_hash, source=f"csv-import:{record.id}", row_count=len(orders))
        db.add(snapshot)
        record.status = "published"
        record.staged_json = []
        record.preview_json = []
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"id": record.id, "status": record.status, "accepted_count": record.accepted_count, "rejected_count": record.rejected_count, "snapshot_id": snapshot.id}
