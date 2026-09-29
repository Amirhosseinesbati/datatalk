import pytest
from datatalk.sql_policy import UnsafeQuery, validate_sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM orders LIMIT 10",
        "SELECT net_revenue_cents FROM analytics_events LIMIT 10; DROP TABLE orders",
        "WITH changed AS (DELETE FROM refunds RETURNING id) SELECT id FROM changed LIMIT 10",
        "SELECT pg_sleep(120) FROM analytics_events LIMIT 10",
        "SELECT net_revenue_cents FROM pg_catalog.pg_authid LIMIT 10",
        "SELECT net_revenue_cents FROM analytics_events a JOIN analytics_events b ON a.order_id=b.order_id LIMIT 10",
        "SELECT net_revenue_cents FROM analytics_events",
        "SELECT net_revenue_cents FROM analytics_events LIMIT 1000000",
        "SELECT net_revenue_cents FROM analytics_events LIMIT 20 OFFSET 1000000000",
    ],
)
def test_sql_ast_policy_rejects_unsafe_queries(sql):
    with pytest.raises(UnsafeQuery):
        validate_sql(sql)


def test_sql_ast_policy_accepts_bounded_aggregation():
    validate_sql("SELECT channel_name AS channel, SUM(net_revenue_cents) AS net_revenue_cents FROM analytics_events WHERE workspace_id = :workspace_id GROUP BY channel_name ORDER BY net_revenue_cents DESC LIMIT 20")
