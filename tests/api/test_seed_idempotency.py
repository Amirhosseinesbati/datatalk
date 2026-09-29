"""A repeat demo bootstrap must not remove published workspace imports."""

import hashlib
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from datatalk import cli
from datatalk.database import Base, make_engine
from datatalk.models import (
    Channel,
    Customer,
    DataImport,
    DatasetSnapshot,
    Order,
    User,
    Workspace,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

def test_same_manifest_load_preserves_published_import_rows(tmp_path, monkeypatch):
    manifest = {"reference_date": "2026-09-28"}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "workspaces.csv").write_text("id,name\nws-northstar,Northstar Supply\n", encoding="utf-8")
    content_hash = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Workspace(id="ws-northstar", name="Northstar Supply"))
        db.flush()
        db.add(User(id="u", workspace_id="ws-northstar", email="u@example.com", password_hash="x", role="admin"))
        db.add(Customer(id="c", workspace_id="ws-northstar", name="Imported Customer", email=None, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        db.add(Channel(id="ch", workspace_id="ws-northstar", name="Direct"))
        db.add(DatasetSnapshot(id="seed", workspace_id="ws-northstar", reference_date="2026-09-28", content_hash=content_hash, source="seed", row_count=0))
        db.flush()
        db.add(Order(id="imported-order", workspace_id="ws-northstar", customer_id="c", channel_id="ch", campaign_id=None, ordered_at=datetime(2026, 2, 1, tzinfo=timezone.utc), status="completed", currency="USD", discount_cents=0))
        db.add(DataImport(id="imported", workspace_id="ws-northstar", user_id="u", status="published", filename="sales.csv", content_hash="import", accepted_count=1, rejected_count=0, errors_json=[], preview_json=[], staged_json=[]))
        db.commit()
    monkeypatch.setattr(cli, "engine", engine)
    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(datatalk_mode="demo"))
    try:
        cli.load_data(tmp_path)
        with Session(engine) as db:
            assert db.get(Order, "imported-order") is not None
            assert db.get(DataImport, "imported").status == "published"
            assert db.scalars(select(DatasetSnapshot)).all()[0].id == "seed"
    finally:
        engine.dispose()
