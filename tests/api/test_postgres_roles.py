"""Database privileges and view scoping must work without the API SQL validator."""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


@pytest.fixture(scope="module")
def reader_engine():
    url = os.environ.get("DATATALK_TEST_ANALYTICS_URL")
    if not url:
        pytest.skip("Set DATATALK_TEST_ANALYTICS_URL for PostgreSQL role checks")
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()


def test_reader_cannot_select_base_orders(reader_engine):
    with reader_engine.connect() as connection, pytest.raises(DBAPIError):
        connection.execute(text("SELECT id FROM orders LIMIT 1")).first()


def test_reader_cannot_update_or_create_even_without_sql_policy(reader_engine):
    with reader_engine.connect() as connection, pytest.raises(DBAPIError):
        connection.execute(text("UPDATE orders SET status = status WHERE 1 = 0"))
    with reader_engine.connect() as connection, pytest.raises(DBAPIError):
        connection.execute(text("CREATE TEMP TABLE datatalk_reader_write_probe (id integer)"))


def test_reader_views_are_scoped_by_transaction_workspace(reader_engine):
    counts = []
    for workspace_id in ("ws-northstar", "ws-eastwind"):
        with reader_engine.connect() as connection:
            connection.execute(text("SELECT set_config('datatalk.workspace_id', :workspace_id, true)"), {"workspace_id": workspace_id})
            count = connection.scalar(text("SELECT COUNT(*) FROM analytics_customer_cohorts"))
            counts.append(count)
            visible = connection.execute(text("SELECT DISTINCT workspace_id FROM analytics_customer_cohorts")).scalars().all()
            assert visible == [workspace_id]
    assert counts[0] > counts[1] > 0
