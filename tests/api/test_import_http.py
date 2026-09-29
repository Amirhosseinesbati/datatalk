"""Exercise the authenticated CSV preview and transactional publish HTTP path."""

import csv
import io

from datatalk.auth import hash_password
from datatalk.database import Base, get_session
from datatalk.imports import TEMPLATE_COLUMNS
from datatalk.main import app
from datatalk.models import DatasetSnapshot, Order, User, Workspace
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def _row(order_id: str, customer_name: str = "Customer") -> dict[str, str]:
    return {
        "order_id": order_id, "customer_id": "customer-one", "customer_name": customer_name,
        "customer_email": "customer@example.com", "ordered_at": "2026-02-05T10:00:00+00:00",
        "channel": "Direct", "product_id": "product-one", "product_name": "Product One",
        "category": "Category", "quantity": "1", "unit_price_cents": "1000",
        "discount_cents": "100", "status": "completed", "currency": "USD",
    }


def _payload(rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=TEMPLATE_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def test_authenticated_import_preview_publish_and_retry():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Workspace(id="w", name="Fixture"))
        db.flush()
        db.add(User(id="u", workspace_id="w", email="manager@example.com", password_hash=hash_password("Password123!"), role="admin"))
        db.commit()

    def test_session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_session] = test_session
    try:
        with TestClient(app) as client:
            login = client.post("/api/auth/login", json={"email": "manager@example.com", "password": "Password123!"})
            assert login.status_code == 200
            rows = [_row("bad-order"), _row("bad-order", "Different Name"), {**_row("good-order"), "customer_id": "customer-two"}]
            preview = client.post("/api/imports/preview", files={"file": ("sales.csv", _payload(rows), "text/csv")})
            assert preview.status_code == 200
            preview_body = preview.json()
            assert preview_body["accepted_count"] == 1
            assert preview_body["rejected_count"] >= 2
            token = preview_body["token"]
            first = client.post("/api/imports/publish", json={"token": token})
            second = client.post("/api/imports/publish", json={"token": token})
            assert first.status_code == second.status_code == 200
            assert first.json()["status"] == second.json()["status"] == "published"
            invalid = client.post("/api/imports/preview", files={"file": ("sales.csv", _payload(rows[:2]), "text/csv")})
            assert invalid.status_code == 200
            assert invalid.json()["accepted_count"] == 0
            refused = client.post("/api/imports/publish", json={"token": invalid.json()["token"]})
            assert refused.status_code == 400
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(Order)) == 1
            assert db.scalar(select(func.count()).select_from(DatasetSnapshot)) == 1
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
