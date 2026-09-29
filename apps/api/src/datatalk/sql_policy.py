"""SQL AST allowlist; DB role and transaction are independent defense layers."""
import sqlglot
from sqlglot import exp


class UnsafeQuery(ValueError):
    pass


ALLOWED_VIEWS = {"analytics_events", "analytics_customer_cohorts"}
ALLOWED_COLUMNS = {
    "workspace_id", "order_id", "order_line_id", "customer_id", "customer_name",
    "channel_id", "channel_name", "product_id", "product_name", "category",
    "campaign_id", "campaign_name", "event_at", "customer_order_number", "currency",
    "gross_sales_cents", "discounts_cents", "refunds_cents", "net_revenue_cents", "event_kind",
    "first_order_at", "next_order_at", "repeat_within_90d",
}
ALLOWED_FUNCTIONS = {"SUM", "COUNT", "ROUND", "NULLIF", "COALESCE", "ABS", "DATE_TRUNC", "TIMESTAMP_TRUNC", "STRFTIME", "AND", "CASE", "IF"}


def validate_sql(sql: str, dialect: str = "postgres", row_cap: int = 200) -> None:
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except sqlglot.ParseError as exc:
        raise UnsafeQuery("SQL could not be parsed") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise UnsafeQuery("Only one SELECT statement is permitted")
    query = statements[0]
    if query.args.get("with") or query.args.get("with_") or query.args.get("into"):
        raise UnsafeQuery("CTEs and SELECT INTO are not permitted")
    if query.args.get("offset") or query.find(exp.Offset):
        raise UnsafeQuery("OFFSET is not permitted")
    forbidden_types = (exp.Subquery, exp.Join, exp.Union, exp.Intersect, exp.Except, exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Command, exp.Window)
    if any(isinstance(node, forbidden_types) for node in query.walk()):
        raise UnsafeQuery("Query contains a forbidden operation")
    tables = list(query.find_all(exp.Table))
    if len(tables) != 1 or tables[0].name not in ALLOWED_VIEWS or tables[0].db or tables[0].catalog:
        raise UnsafeQuery("Only one allowlisted analytical view may be read")
    aliases = {alias.alias for alias in query.find_all(exp.Alias)}
    for column in query.find_all(exp.Column):
        if column.name not in ALLOWED_COLUMNS | aliases or column.table:
            raise UnsafeQuery(f"Identifier is not allowlisted: {column.name}")
    for function in query.find_all(exp.Func):
        name = function.sql_name().upper() if hasattr(function, "sql_name") else function.key.upper()
        if name not in ALLOWED_FUNCTIONS:
            raise UnsafeQuery(f"Function is not allowlisted: {name}")
    limit = query.args.get("limit")
    if not limit or not isinstance(limit.expression, exp.Literal) or not limit.expression.is_int:
        raise UnsafeQuery("A numeric row limit is required")
    if int(limit.expression.this) < 1 or int(limit.expression.this) > row_cap:
        raise UnsafeQuery("Row limit exceeds the policy cap")
    if query.find(exp.Star):
        raise UnsafeQuery("Wildcard selection is not permitted")
