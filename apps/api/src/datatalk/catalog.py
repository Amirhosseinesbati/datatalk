"""Business definitions shared by planning, API and report evidence."""

METRICS = [
    {"key": "gross_sales", "name": "Gross sales", "definition": "Sum of completed order-line quantity times unit price before discounts and refunds.", "unit": "usd_cents", "column": "gross_sales_cents"},
    {"key": "discounts", "name": "Discounts", "definition": "Sum of line-level discounts on completed orders. Order discount is a denormalized reconciliation field and is not subtracted again.", "unit": "usd_cents", "column": "discounts_cents"},
    {"key": "refunds", "name": "Refunds", "definition": "Sum of completed-order refund amounts attributed to the refund event date.", "unit": "usd_cents", "column": "refunds_cents"},
    {"key": "net_revenue", "name": "Net revenue", "definition": "Completed-order gross sales minus line discounts at order date, minus refunds at refund date; USD cents.", "unit": "usd_cents", "column": "net_revenue_cents"},
    {"key": "completed_orders", "name": "Completed orders", "definition": "Distinct completed order IDs; cancelled orders contribute nothing.", "unit": "count", "column": "completed_orders"},
    {"key": "average_order_value", "name": "Average order value", "definition": "Completed-order gross sales minus discounts, divided by distinct completed orders in the period. Refunds are tracked separately; zero orders yield null.", "unit": "usd_cents", "column": "average_order_value_cents"},
    {"key": "returning_customers", "name": "Returning customers", "definition": "Distinct customers whose completed order was their second or later completed order at the time of purchase.", "unit": "count", "column": "returning_customers"},
    {"key": "cancelled_orders", "name": "Cancelled orders", "definition": "Distinct cancelled orders counted on their order date. They contribute no gross sales or revenue.", "unit": "count", "column": "cancelled_orders"},
    {"key": "repeat_customers_90d", "name": "90-day repeat customers", "definition": "Customers whose first completed order is in the cohort period and who placed a strictly later completed order within 90 days.", "unit": "count", "column": "repeat_customers_90d"},
]

DIMENSIONS = [
    {"key": "channel", "name": "Sales channel", "column": "channel_name"},
    {"key": "product", "name": "Product", "column": "product_name"},
    {"key": "category", "name": "Product category", "column": "category"},
    {"key": "customer", "name": "Customer", "column": "customer_name"},
    {"key": "campaign", "name": "Campaign", "column": "campaign_name"},
    {"key": "day", "name": "Day (UTC)", "column": "event_at"},
    {"key": "week", "name": "Week (UTC)", "column": "event_at"},
    {"key": "month", "name": "Month (UTC)", "column": "event_at"},
]

METRIC_BY_KEY = {item["key"]: item for item in METRICS}
DIMENSION_BY_KEY = {item["key"]: item for item in DIMENSIONS}

DATE_CONVENTIONS = {
    "timezone": "UTC",
    "interval": "[start, end)",
    "sales_basis": "completed order date",
    "refund_basis": "refund event timestamp",
    "currency": "USD",
}

SOURCE_TABLES = ["orders", "order_lines", "refunds", "customers", "products", "channels", "campaigns"]


def public_catalog() -> dict:
    return {
        "metrics": [{k: v for k, v in item.items() if k != "column"} for item in METRICS],
        "dimensions": [{k: v for k, v in item.items() if k != "column"} for item in DIMENSIONS],
        "date_conventions": DATE_CONVENTIONS,
        "source_tables": SOURCE_TABLES,
    }
