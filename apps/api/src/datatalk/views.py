"""Allowlisted analytical views. Postgres embeds workspace isolation in each view."""
import re
from sqlalchemy import text
from sqlalchemy.engine import Engine
from .config import get_settings


def create_views(engine: Engine) -> None:
    postgres = engine.dialect.name == "postgresql"
    barrier = "WITH (security_barrier = true)" if postgres else ""
    workspace_guard = "AND o.workspace_id = current_setting('datatalk.workspace_id', true)" if postgres else ""
    refund_guard = "AND r.workspace_id = current_setting('datatalk.workspace_id', true)" if postgres else ""
    sales_sql = f"""
    CREATE VIEW analytics_sales {barrier} AS
    WITH ranked_orders AS (
      SELECT o.id, ROW_NUMBER() OVER (PARTITION BY o.workspace_id, o.customer_id ORDER BY o.ordered_at, o.id) AS customer_order_number
      FROM orders o WHERE o.status = 'completed'
    )
    SELECT o.workspace_id, o.id AS order_id, ol.id AS order_line_id, o.customer_id,
      c.name AS customer_name, o.channel_id, ch.name AS channel_name,
      ol.product_id, p.name AS product_name, p.category,
      o.campaign_id, ca.name AS campaign_name, o.ordered_at AS event_at,
      ro.customer_order_number, o.currency, 'sale' AS event_kind,
      ol.quantity * ol.unit_price_cents AS gross_sales_cents,
      ol.discount_cents AS discounts_cents,
      0 AS refunds_cents,
      ol.quantity * ol.unit_price_cents - ol.discount_cents AS net_revenue_cents
    FROM orders o
    JOIN order_lines ol ON ol.order_id = o.id AND ol.workspace_id = o.workspace_id
    JOIN customers c ON c.id = o.customer_id AND c.workspace_id = o.workspace_id
    JOIN channels ch ON ch.id = o.channel_id AND ch.workspace_id = o.workspace_id
    JOIN products p ON p.id = ol.product_id AND p.workspace_id = o.workspace_id
    JOIN ranked_orders ro ON ro.id = o.id
    LEFT JOIN campaigns ca ON ca.id = o.campaign_id AND ca.workspace_id = o.workspace_id
    WHERE o.status = 'completed' {workspace_guard}
    """
    refunds_sql = f"""
    CREATE VIEW analytics_refunds {barrier} AS
    SELECT r.workspace_id, o.id AS order_id, ol.id AS order_line_id, o.customer_id,
      c.name AS customer_name, o.channel_id, ch.name AS channel_name,
      ol.product_id, p.name AS product_name, p.category,
      o.campaign_id, ca.name AS campaign_name, r.refunded_at AS event_at,
      0 AS customer_order_number, o.currency, 'refund' AS event_kind, 0 AS gross_sales_cents,
      0 AS discounts_cents, r.amount_cents AS refunds_cents,
      -r.amount_cents AS net_revenue_cents
    FROM refunds r
    JOIN order_lines ol ON ol.id = r.order_line_id AND ol.workspace_id = r.workspace_id
    JOIN orders o ON o.id = ol.order_id AND o.workspace_id = r.workspace_id
    JOIN customers c ON c.id = o.customer_id AND c.workspace_id = r.workspace_id
    JOIN channels ch ON ch.id = o.channel_id AND ch.workspace_id = r.workspace_id
    JOIN products p ON p.id = ol.product_id AND p.workspace_id = r.workspace_id
    LEFT JOIN campaigns ca ON ca.id = o.campaign_id AND ca.workspace_id = r.workspace_id
    WHERE o.status = 'completed' {refund_guard}
    """
    cancellations_sql = f"""
    CREATE VIEW analytics_cancellations {barrier} AS
    SELECT o.workspace_id, o.id AS order_id, NULL AS order_line_id, o.customer_id,
      c.name AS customer_name, o.channel_id, ch.name AS channel_name,
      NULL AS product_id, NULL AS product_name, NULL AS category,
      o.campaign_id, ca.name AS campaign_name, o.ordered_at AS event_at,
      0 AS customer_order_number, o.currency, 'cancelled' AS event_kind,
      0 AS gross_sales_cents, 0 AS discounts_cents, 0 AS refunds_cents,
      0 AS net_revenue_cents
    FROM orders o
    JOIN customers c ON c.id = o.customer_id AND c.workspace_id = o.workspace_id
    JOIN channels ch ON ch.id = o.channel_id AND ch.workspace_id = o.workspace_id
    LEFT JOIN campaigns ca ON ca.id = o.campaign_id AND ca.workspace_id = o.workspace_id
    WHERE o.status = 'cancelled' {workspace_guard}
    """
    cohort_guard = "WHERE f.workspace_id = current_setting('datatalk.workspace_id', true)" if postgres else ""
    repeat_condition = "next_order_at < first_order_at + INTERVAL '90 days'" if postgres else "JULIANDAY(next_order_at) - JULIANDAY(first_order_at) < 90"
    cohort_sql = f"""
    CREATE VIEW analytics_customer_cohorts {barrier} AS
    WITH firsts AS (
      SELECT workspace_id, customer_id, MIN(ordered_at) AS first_order_at
      FROM orders WHERE status = 'completed' GROUP BY workspace_id, customer_id
    ), nexts AS (
      SELECT f.workspace_id, f.customer_id, f.first_order_at,
      (SELECT MIN(o2.ordered_at) FROM orders o2
       WHERE o2.workspace_id = f.workspace_id AND o2.customer_id = f.customer_id
       AND o2.status = 'completed' AND o2.ordered_at > f.first_order_at) AS next_order_at
      FROM firsts f
    )
    SELECT f.workspace_id, f.customer_id, f.first_order_at, f.next_order_at,
      CASE WHEN f.next_order_at IS NOT NULL AND {repeat_condition} THEN 1 ELSE 0 END AS repeat_within_90d
    FROM nexts f {cohort_guard}
    """
    events_sql = f"""
    CREATE VIEW analytics_events {barrier} AS
    SELECT * FROM analytics_sales
    UNION ALL
    SELECT * FROM analytics_refunds
    UNION ALL
    SELECT * FROM analytics_cancellations
    """
    with engine.begin() as connection:
        exists = connection.execute(text("SELECT to_regclass('public.analytics_events')") if postgres else text("SELECT name FROM sqlite_master WHERE type='view' AND name='analytics_events'")).scalar_one_or_none()
        cancellation_exists = connection.execute(text("SELECT to_regclass('public.analytics_cancellations')") if postgres else text("SELECT name FROM sqlite_master WHERE type='view' AND name='analytics_cancellations'")).scalar_one_or_none()
        cohort_exists = connection.execute(text("SELECT to_regclass('public.analytics_customer_cohorts')") if postgres else text("SELECT name FROM sqlite_master WHERE type='view' AND name='analytics_customer_cohorts'")).scalar_one_or_none()
        if not exists or not cancellation_exists:
            connection.execute(text("DROP VIEW IF EXISTS analytics_events"))
            connection.execute(text("DROP VIEW IF EXISTS analytics_refunds"))
            connection.execute(text("DROP VIEW IF EXISTS analytics_sales"))
            connection.execute(text("DROP VIEW IF EXISTS analytics_cancellations"))
            connection.execute(text(sales_sql))
            connection.execute(text(refunds_sql))
            connection.execute(text(cancellations_sql))
            connection.execute(text(events_sql))
        if not cohort_exists:
            connection.execute(text(cohort_sql))
        if postgres:
            settings = get_settings()
            for role in (settings.datatalk_app_role, settings.datatalk_reader_role):
                if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
                    raise ValueError("invalid database role name")
            role_rows: list[str] = list(connection.execute(text("SELECT rolname FROM pg_roles WHERE rolname IN (:app, :reader)"), {"app": settings.datatalk_app_role, "reader": settings.datatalk_reader_role}).scalars())
            if settings.datatalk_app_role in role_rows:
                connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {settings.datatalk_app_role}"))
                connection.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {settings.datatalk_app_role}"))
                connection.execute(text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {settings.datatalk_app_role}"))
            if settings.datatalk_reader_role in role_rows:
                connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {settings.datatalk_reader_role}"))
                connection.execute(text(f"GRANT SELECT ON analytics_events, analytics_customer_cohorts TO {settings.datatalk_reader_role}"))
