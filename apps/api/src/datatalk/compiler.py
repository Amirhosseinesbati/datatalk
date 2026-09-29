"""Only fixed identifiers are interpolated; user-controlled values stay bound parameters."""
from dataclasses import dataclass
from .schemas import QueryPlan


@dataclass(frozen=True)
class CompiledQuery:
    sql: str
    params: dict
    source_view: str
    source_tables: list[str]


DIMENSIONS = {
    "channel": "channel_name", "product": "product_name", "category": "category",
    "customer": "customer_name", "campaign": "campaign_name",
}
FILTER_COLUMNS = {"channel": "channel_name", "category": "category", "product": "product_name", "customer": "customer_name", "campaign": "campaign_name"}
SUM_COLUMNS = {"gross_sales": "gross_sales_cents", "discounts": "discounts_cents", "refunds": "refunds_cents", "net_revenue": "net_revenue_cents"}


def _metric_expression(metric: str, condition: str | None = None) -> str:
    if metric in SUM_COLUMNS:
        column = SUM_COLUMNS[metric]
        return f"COALESCE(SUM(CASE WHEN {condition} THEN {column} ELSE 0 END), 0)" if condition else f"COALESCE(SUM({column}), 0)"
    if metric == "completed_orders":
        predicate = "event_kind = 'sale'"
        if condition:
            predicate += f" AND {condition}"
        value = f"CASE WHEN {predicate} THEN order_id END"
        return f"COUNT(DISTINCT {value})"
    if metric == "cancelled_orders":
        predicate = "event_kind = 'cancelled'"
        if condition:
            predicate += f" AND {condition}"
        return f"COUNT(DISTINCT CASE WHEN {predicate} THEN order_id END)"
    if metric == "returning_customers":
        predicate = "event_kind = 'sale' AND customer_order_number > 1"
        if condition:
            predicate += f" AND {condition}"
        return f"COUNT(DISTINCT CASE WHEN {predicate} THEN customer_id END)"
    if metric == "average_order_value":
        gross = _metric_expression("gross_sales", condition)
        discounts = _metric_expression("discounts", condition)
        numerator = f"({gross} - {discounts})"
        denominator = _metric_expression("completed_orders", condition)
        return f"ROUND(1.0 * {numerator} / NULLIF({denominator}, 0), 2)"
    raise ValueError("unsupported metric")


def compile_plan(plan: QueryPlan, workspace_id: str, dialect: str = "postgresql", row_cap: int = 200) -> CompiledQuery:
    if plan.metrics == ["repeat_customers_90d"]:
        if plan.dimensions or plan.comparison != "none":
            raise ValueError("90-day cohort metric currently supports one period without grouping")
        sql = "SELECT COUNT(customer_id) AS repeat_customers_90d FROM analytics_customer_cohorts WHERE workspace_id = :workspace_id AND first_order_at >= :start_at AND first_order_at < :end_at AND repeat_within_90d = 1 LIMIT 1"
        return CompiledQuery(sql=sql, params={"workspace_id": workspace_id, "start_at": plan.start_date.isoformat(), "end_at": plan.end_date.isoformat()}, source_view="analytics_customer_cohorts", source_tables=["orders"])
    view = "analytics_events"
    params: dict = {"workspace_id": workspace_id, "start_at": plan.start_date.isoformat(), "end_at": plan.end_date.isoformat(), "currency": "USD"}
    dimensions: list[tuple[str, str]] = []
    for dimension in plan.dimensions:
        if dimension in DIMENSIONS:
            dimensions.append((DIMENSIONS[dimension], dimension))
        else:
            if dialect == "postgresql":
                unit = "day" if dimension == "day" else "week" if dimension == "week" else "month"
                expression = f"DATE_TRUNC('{unit}', event_at)"
            else:
                fmt = "%Y-%m-%d" if dimension == "day" else "%Y-%W" if dimension == "week" else "%Y-%m"
                expression = f"STRFTIME('{fmt}', event_at)"
            dimensions.append((expression, dimension))
    select = [f"{expr} AS {alias}" for expr, alias in dimensions]
    where = ["workspace_id = :workspace_id", "currency = :currency", "event_at < :end_at"]
    if plan.metrics == ["cancelled_orders"]:
        where.append("event_kind = 'cancelled'")
    elif "cancelled_orders" not in plan.metrics:
        where.append("event_kind != 'cancelled'")
    if plan.comparison == "previous_period":
        days = plan.end_date - plan.start_date
        params["previous_start_at"] = (plan.start_date - days).isoformat()
        where.append("event_at >= :previous_start_at")
    else:
        where.append("event_at >= :start_at")
    for key, column in FILTER_COLUMNS.items():
        value = getattr(plan, key)
        if value:
            params[key] = value
            where.append(f"{column} = :{key}")
    if plan.comparison == "previous_period":
        metric = plan.metrics[0]
        current = _metric_expression(metric, "event_at >= :start_at AND event_at < :end_at")
        previous = _metric_expression(metric, "event_at >= :previous_start_at AND event_at < :start_at")
        select += [f"{current} AS current_value", f"{previous} AS previous_value", f"({current} - {previous}) AS change"]
        select.append(f"ROUND(100.0 * ({current} - {previous}) / NULLIF({previous}, 0), 2) AS growth_percent")
        sort_expr = f"ABS(({current} - {previous})) DESC" if plan.sort == "absolute_change_desc" else "change DESC"
    else:
        for metric in plan.metrics:
            alias = "average_order_value_cents" if metric == "average_order_value" else f"{metric}_cents" if metric in SUM_COLUMNS else metric
            select.append(f"{_metric_expression(metric)} AS {alias}")
        first_alias = "average_order_value_cents" if plan.metrics[0] == "average_order_value" else f"{plan.metrics[0]}_cents" if plan.metrics[0] in SUM_COLUMNS else plan.metrics[0]
        sort_expr = f"{first_alias} ASC" if plan.sort == "value_asc" else f"{dimensions[0][1]} ASC" if plan.sort == "dimension_asc" and dimensions else f"{first_alias} DESC"
    grouping = f" GROUP BY {', '.join(expr for expr, _ in dimensions)}" if dimensions else ""
    limit = min(plan.top_n, row_cap) + 1
    sql = f"SELECT {', '.join(select)} FROM {view} WHERE {' AND '.join(where)}{grouping} ORDER BY {sort_expr} LIMIT {limit}"
    return CompiledQuery(sql=sql, params=params, source_view=view, source_tables=["orders", "order_lines", "refunds", "customers", "products", "channels", "campaigns"])
