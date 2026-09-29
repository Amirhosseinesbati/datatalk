import json
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from datatalk.compiler import compile_plan
from datatalk.database import Base, make_engine
from datatalk.executor import QueryExecutor
from datatalk.models import Workspace, Customer, Product, Channel, Order, OrderLine, Refund
from datatalk.schemas import QueryPlan
from datatalk.views import create_views


def metric_fixture_engine():
    root = Path(__file__).resolve().parents[2]
    fixture = json.loads((root / "fixtures" / "metric_invariants.json").read_text(encoding="utf-8"))
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    create_views(engine)
    with Session(engine) as db:
        db.add(Workspace(id="w", name="Fixture"))
        db.flush()
        db.add(Customer(id="c", workspace_id="w", name="Customer", email="c@example.com", created_at=datetime.fromisoformat("2025-01-01T00:00:00+00:00")))
        db.add(Product(id="p", workspace_id="w", name="Product", category="Category", cost_cents=100))
        db.add(Channel(id="ch", workspace_id="w", name="Direct"))
        db.flush()
        for item in fixture["orders"]:
            db.add(Order(id=item["id"], workspace_id="w", customer_id="c", channel_id="ch", campaign_id=None, ordered_at=datetime.fromisoformat(item["ordered_at"]), status=item["status"], currency="USD", discount_cents=item["discount_cents"]))
        db.flush()
        for item in fixture["order_lines"]:
            db.add(OrderLine(id=item["id"], workspace_id="w", order_id=item["order_id"], product_id="p", quantity=item["quantity"], unit_price_cents=item["unit_price_cents"], discount_cents=item["discount_cents"]))
        db.flush()
        for item in fixture["refunds"]:
            db.add(Refund(id=item["id"], workspace_id="w", order_line_id=item["order_line_id"], refunded_at=datetime.fromisoformat(item["refunded_at"]), amount_cents=item["amount_cents"], reason="fixture"))
        db.commit()
    return engine, fixture


def _value(engine, metric: str, month: str):
    start = datetime.strptime(month, "%Y-%m").date()
    end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    plan = QueryPlan(metrics=[metric], start_date=start, end_date=end)
    compiled = compile_plan(plan, "w", dialect="sqlite")
    result = QueryExecutor(engine).execute(compiled.sql, compiled.params, "w", 20)
    return result["rows"][0][result["columns"][0]]


def test_delayed_refund_cancelled_order_discount_and_zero_denominator():
    engine, fixture = metric_fixture_engine()
    try:
        for month, expected in fixture["expected_months"].items():
            for key, value in expected.items():
                metric = key[:-6] if key.endswith("_cents") else key
                assert _value(engine, metric, month) == value, (month, key)
        assert _value(engine, "cancelled_orders", "2026-02") == 1
        assert _value(engine, "returning_customers", "2026-02") == 1
        assert _value(engine, "repeat_customers_90d", "2026-01") == 1
        category_plan = QueryPlan(metrics=["net_revenue"], dimensions=["category"], start_date=datetime(2026, 2, 1).date(), end_date=datetime(2026, 3, 1).date())
        category_sql = compile_plan(category_plan, "w", dialect="sqlite")
        category_result = QueryExecutor(engine).execute(category_sql.sql, category_sql.params, "w", 20)
        assert len(category_result["rows"]) == 1
        assert category_result["rows"][0]["category"] == "Category"
    finally:
        engine.dispose()
