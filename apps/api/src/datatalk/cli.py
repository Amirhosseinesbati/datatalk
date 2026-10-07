"""Database bootstrap, reproducible CSV loading, and first-user setup."""
import argparse
import csv
import getpass
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
from sqlalchemy import delete, insert, select, update
from .auth import hash_password
from .catalog import METRICS
from .config import get_settings
from .database import engine
from .models import (
    Workspace, User, Customer, Product, Channel, Campaign, CampaignEvent,
    InventoryEvent, Order, OrderLine, Refund, MetricDefinition, DatasetSnapshot, DataImport,
)
from .views import create_views


TABLES = [Workspace, Customer, Product, Channel, Campaign, CampaignEvent, InventoryEvent, Order, OrderLine, Refund]
TIME_FIELDS = {"created_at", "starts_at", "ends_at", "event_at", "ordered_at", "refunded_at"}
INT_FIELDS = {"quantity", "cost_cents", "discount_cents", "unit_price_cents", "amount_cents"}


def init_db() -> None:
    from alembic import command
    from alembic.config import Config
    from langgraph.checkpoint.postgres import PostgresSaver

    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    command.upgrade(config, "head")
    if engine.dialect.name == "postgresql":
        url = get_settings().database_url.replace("+psycopg", "")
        with PostgresSaver.from_conn_string(url) as saver:
            saver.setup()
    create_views(engine)
    with engine.begin() as connection:
        for metric in METRICS:
            existing = connection.execute(select(MetricDefinition.id).where(MetricDefinition.key == metric["key"])).scalar_one_or_none()
            payload = {k: metric[k] for k in ("key", "name", "definition", "unit")}
            if existing:
                connection.execute(update(MetricDefinition).where(MetricDefinition.id == existing).values(**payload))
            else:
                connection.execute(insert(MetricDefinition), [{"id": str(uuid4()), **payload}])


def _typed_row(row: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if value == "":
            result[key] = None
        elif key in TIME_FIELDS:
            result[key] = datetime.fromisoformat(value)
        elif key in INT_FIELDS:
            result[key] = int(value)
        elif key == "details_json":
            result[key] = json.loads(value)
        else:
            result[key] = value
    return result


def _verify_manifest(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    for filename, expected_hash in manifest.get("files_sha256", {}).items():
        if hashlib.sha256((directory / filename).read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f"Seed file failed SHA256 verification: {filename}")
    return manifest


def load_data(directory: Path, reset_demo: bool = False) -> None:
    if get_settings().datatalk_mode != "demo":
        raise ValueError("Bundled seed loading is only permitted in DEMO mode")
    manifest = _verify_manifest(directory)
    with (directory / "workspaces.csv").open(newline="", encoding="utf-8") as handle:
        workspaces = list(csv.DictReader(handle))
    ids = [row["id"] for row in workspaces]
    if not ids:
        raise ValueError("dataset has no workspaces")
    if not set(ids).issubset({"ws-northstar", "ws-eastwind"}):
        raise ValueError("seed contains a non-demo workspace ID")
    content_hash = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with engine.begin() as connection:
        loaded = connection.execute(select(DatasetSnapshot.workspace_id).where(DatasetSnapshot.workspace_id.in_(ids), DatasetSnapshot.content_hash == content_hash)).scalars().all()
        if set(loaded) == set(ids):
            return
        if not reset_demo:
            published = connection.execute(select(DataImport.id).where(DataImport.workspace_id.in_(ids), DataImport.status == "published").limit(1)).scalar_one_or_none()
            if published:
                raise ValueError("Published demo imports exist. Pass --reset-demo to explicitly replace demo data.")
        for row in workspaces:
            exists = connection.execute(select(Workspace.id).where(Workspace.id == row["id"])).scalar_one_or_none()
            if exists:
                connection.execute(update(Workspace).where(Workspace.id == exists).values(name=row["name"]))
            else:
                connection.execute(insert(Workspace), [row])
        for model in reversed(TABLES[1:]):
            table = model.__table__
            connection.execute(delete(model).where(table.c.workspace_id.in_(ids)))
        for model in TABLES[1:]:
            path = directory / f"{model.__tablename__}.csv"
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                batch = []
                for row in reader:
                    batch.append(_typed_row(row))
                    if len(batch) >= 1000:
                        connection.execute(insert(model), batch)
                        batch = []
                if batch:
                    connection.execute(insert(model), batch)
        for workspace_id in ids:
            previous = connection.execute(select(DatasetSnapshot.id).where(DatasetSnapshot.workspace_id == workspace_id, DatasetSnapshot.content_hash == content_hash)).scalar_one_or_none()
            if not previous:
                connection.execute(insert(DatasetSnapshot), [{"id": str(uuid4()), "workspace_id": workspace_id, "reference_date": manifest["reference_date"], "content_hash": content_hash, "source": f"synthetic-seed:{directory}", "row_count": manifest.get("counts_by_workspace", {}).get(workspace_id, {}).get("orders", 0)}])
    if get_settings().datatalk_mode == "demo":
        _seed_demo_users(workspaces)


def _seed_demo_users(workspaces: list[dict]) -> None:
    password = hash_password(get_settings().datatalk_demo_password)
    northstar = next((row["id"] for row in workspaces if "northstar" in row["name"].lower()), workspaces[0]["id"])
    eastwind = next((row["id"] for row in workspaces if row["id"] != northstar), None)
    accounts = [("manager@northstar.example.com", northstar, "admin"), ("operator@northstar.example.com", northstar, "operator"), ("viewer@northstar.example.com", northstar, "viewer")]
    if eastwind:
        accounts.append(("manager@eastwind.example.com", eastwind, "admin"))
    with engine.begin() as connection:
        for email, workspace_id, role in accounts:
            exists = connection.execute(select(User.id).where(User.email == email)).scalar_one_or_none()
            if not exists:
                connection.execute(insert(User), [{"id": str(uuid4()), "workspace_id": workspace_id, "email": email, "password_hash": password, "role": role, "is_demo": True}])


def create_user(email: str, password: str, workspace_id: str, role: str) -> None:
    if role not in {"admin", "operator", "viewer"}:
        raise ValueError("role must be admin, operator or viewer")
    with engine.begin() as connection:
        if not connection.execute(select(Workspace.id).where(Workspace.id == workspace_id)).scalar_one_or_none():
            raise ValueError("unknown workspace")
        if connection.execute(select(User.id).where(User.email == email)).scalar_one_or_none():
            raise ValueError("email already exists")
        connection.execute(insert(User), [{"id": str(uuid4()), "workspace_id": workspace_id, "email": email, "password_hash": hash_password(password), "role": role, "is_demo": False}])


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    loader = sub.add_parser("load-data")
    loader.add_argument("--dir", required=True, type=Path)
    loader.add_argument("--reset-demo", action="store_true")
    user = sub.add_parser("create-user")
    user.add_argument("--email", required=True)
    user.add_argument("--password-env", help="Environment variable containing the new password; otherwise prompt securely")
    user.add_argument("--workspace-id", required=True)
    user.add_argument("--role", required=True)
    args = parser.parse_args()
    if args.command == "init-db":
        init_db()
    elif args.command == "load-data":
        load_data(args.dir, args.reset_demo)
    else:
        password = os.environ.get(args.password_env) if args.password_env else getpass.getpass("Password: ")
        if not password:
            raise ValueError("password is required")
        create_user(args.email, password, args.workspace_id, args.role)


if __name__ == "__main__":
    main()
