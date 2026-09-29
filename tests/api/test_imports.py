import asyncio
import csv
import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from datatalk.database import Base, make_engine
from datatalk.imports import TEMPLATE_COLUMNS, expire_import_previews, preview_import, publish_import
from datatalk.models import DataImport, DatasetSnapshot, Order, User, Workspace


def _csv_payload(rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=TEMPLATE_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _row(order_id: str, customer_id: str, name: str = "Customer") -> dict[str, str]:
    return {
        "order_id": order_id,
        "customer_id": customer_id,
        "customer_name": name,
        "customer_email": "customer@example.com",
        "ordered_at": "2026-02-05T10:00:00+00:00",
        "channel": "Direct",
        "product_id": "product-one",
        "product_name": "Product One",
        "category": "Category",
        "quantity": "1",
        "unit_price_cents": "1000",
        "discount_cents": "100",
        "status": "completed",
        "currency": "USD",
    }


def _test_db():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(Workspace(id="w", name="Fixture"))
    db.flush()
    user = User(id="u", workspace_id="w", email="u@example.com", password_hash="x", role="manager")
    db.add(user)
    db.flush()
    return engine, db, user


def _preview(db: Session, user: User, rows: list[dict[str, str]]) -> dict:
    upload = UploadFile(file=io.BytesIO(_csv_payload(rows)), filename="sales.csv")
    return asyncio.run(preview_import(db, user, upload))


def test_import_publish_is_idempotent_and_reference_date_never_moves_backward():
    engine, db, user = _test_db()
    try:
        db.add(DatasetSnapshot(id="prior", workspace_id="w", reference_date="2026-12-31", content_hash="prior", source="seed", row_count=0))
        db.commit()
        common_prefix = "same-prefix-" + "x" * 100
        preview = _preview(db, user, [_row(common_prefix + "a", "customer-a"), _row(common_prefix + "b", "customer-b")])
        assert preview["accepted_count"] == 2
        first = publish_import(db, user, preview["token"])
        second = publish_import(db, user, preview["token"])
        assert first["status"] == second["status"] == "published"
        assert first["snapshot_id"] == second["snapshot_id"]
        db.expire_all()
        import_record = db.get(DataImport, preview["token"])
        assert import_record is not None
        assert import_record.staged_json == []
        assert import_record.preview_json == []
        assert db.scalar(select(func.count()).select_from(Order)) == 2
        assert db.scalar(select(func.count()).select_from(DataImport)) == 1
        snapshot = db.scalars(select(DatasetSnapshot).where(DatasetSnapshot.source == f"csv-import:{preview['token']}")).one()
        assert snapshot.reference_date == "2026-12-31"
        assert db.scalar(select(func.count()).select_from(DatasetSnapshot)) == 2
    finally:
        db.close()
        engine.dispose()


def test_expired_preview_cannot_publish_and_discards_staged_rows():
    engine, db, user = _test_db()
    try:
        preview = _preview(db, user, [_row("order-a", "customer-a")])
        record = db.get(DataImport, preview["token"])
        assert record is not None
        assert record.staged_json
        record.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        db.commit()
        with pytest.raises(HTTPException) as error:
            publish_import(db, user, preview["token"])
        assert error.value.status_code == 410
        db.expire_all()
        record = db.get(DataImport, preview["token"])
        assert record is not None
        assert record.status == "expired"
        assert record.staged_json == record.preview_json == []
        assert db.scalar(select(func.count()).select_from(Order)) == 0
    finally:
        db.close()
        engine.dispose()


def test_cleanup_expires_only_old_unpublished_previews():
    engine, db, user = _test_db()
    try:
        old_preview = _preview(db, user, [_row("order-old", "customer-old")])
        recent_preview = _preview(db, user, [_row("order-new", "customer-new")])
        old_record = db.get(DataImport, old_preview["token"])
        assert old_record is not None
        old_record.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        db.commit()
        assert expire_import_previews(db) == 1
        db.expire_all()
        old_record = db.get(DataImport, old_preview["token"])
        recent_record = db.get(DataImport, recent_preview["token"])
        assert old_record is not None and recent_record is not None
        assert old_record.status == "expired"
        assert old_record.staged_json == old_record.preview_json == []
        assert recent_record.status == "preview"
        assert recent_record.staged_json
    finally:
        db.close()
        engine.dispose()


def test_import_rejects_all_orders_with_conflicting_customer_identity():
    engine, db, user = _test_db()
    try:
        rows = [_row("order-a", "customer-one"), _row("order-b", "customer-one"), _row("order-c", "customer-one", "Different Name")]
        preview = _preview(db, user, rows)
        assert preview["accepted_count"] == 0
        assert preview["rejected_count"] >= 3
        with pytest.raises(HTTPException) as error:
            publish_import(db, user, preview["token"])
        assert error.value.status_code == 400
    finally:
        db.close()
        engine.dispose()
