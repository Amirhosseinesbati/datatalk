"""Chart selection and evidence-bound conclusions from actual query rows."""
from .schemas import QueryPlan


def _display_value(value, money: bool) -> str:
    if value is None:
        return "undefined because the denominator is zero"
    if money:
        amount = float(value) / 100
        return f"-${abs(amount):,.2f}" if amount < 0 else f"${amount:,.2f}"
    return f"{value:,}" if isinstance(value, int) else str(value)


def chart_for(plan: QueryPlan, result: dict) -> dict:
    columns = result["columns"]
    dimension = next((d for d in plan.dimensions if d in columns), None)
    values = [c for c in columns if c not in plan.dimensions]
    if not dimension or not result["rows"]:
        return {"type": "table"}
    chart_type = "line" if dimension in {"day", "week", "month"} else "bar"
    if plan.comparison == "previous_period" and "change" in values:
        return {"type": chart_type, "x": dimension, "y": "change", "series": ["change"]}
    return {"type": chart_type, "x": dimension, "y": values[0] if values else None, "series": values}


def narrative_for(plan: QueryPlan, result: dict) -> tuple[str, dict]:
    rows = result["rows"]
    if not rows:
        return "No matching completed sales records were found for these filters and dates.", {"row_indices": [], "columns": []}
    first = rows[0]
    metric_column = "change" if plan.comparison == "previous_period" else next((c for c in result["columns"] if c not in plan.dimensions), result["columns"][0])
    value = first.get(metric_column)
    money = plan.metrics[0] in {"gross_sales", "discounts", "refunds", "net_revenue", "average_order_value"}
    displayed = _display_value(value, money)
    metric_label = metric_column.replace("_cents", "").replace("_", " ")
    if plan.dimensions:
        label = ", ".join(str(first.get(dim, "Unknown")) for dim in plan.dimensions)
        summary = f"{label} is the first result with {metric_label} of {displayed}."
    else:
        summary = f"{metric_label.capitalize()} is {displayed}."
    if plan.comparison == "previous_period":
        summary += " The comparison uses an equally long preceding UTC period."
    if result["truncated"]:
        summary += f" The table shows only the first {result['row_count']} rows."
    summary += " This is an observed comparison, not evidence of causation."
    return summary, {"row_indices": [0], "columns": [metric_column] + plan.dimensions}
