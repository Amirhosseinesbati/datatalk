"""Validate generated demo data independently of the application database."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


TABLES = ("workspaces", "customers", "products", "channels", "campaigns", "campaign_events", "inventory_events", "orders", "order_lines", "refunds")


def read_rows(directory: Path, table: str) -> list[dict[str, str]]:
    with (directory / f"{table}.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def validate(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    rows = {table: read_rows(directory, table) for table in TABLES}
    for table, table_rows in rows.items():
        assert len(table_rows) == manifest["counts"][table], f"{table}: manifest count mismatch"
        ids = [row["id"] for row in table_rows]
        assert len(ids) == len(set(ids)), f"{table}: duplicate id"
        filename = f"{table}.csv"
        assert hashlib.sha256((directory / filename).read_bytes()).hexdigest() == manifest["files_sha256"][filename], f"{table}: SHA mismatch"

    workspace_ids = {row["id"] for row in rows["workspaces"]}
    by_id = {table: {row["id"]: row for row in rows[table]} for table in TABLES}
    for table, table_rows in rows.items():
        if table == "workspaces":
            continue
        assert all(row["workspace_id"] in workspace_ids for row in table_rows), f"{table}: unknown workspace"
    customers, products, channels, campaigns, orders, lines = (by_id[name] for name in ("customers", "products", "channels", "campaigns", "orders", "order_lines"))

    start = datetime.fromisoformat(manifest["start_at"])
    end = datetime.fromisoformat(manifest["end_at_exclusive"])
    order_discounts: Counter[str] = Counter()
    order_line_count: Counter[str] = Counter()
    refund_total: Counter[str] = Counter()
    workspace_amounts: dict[str, Counter] = defaultdict(Counter)
    order_statuses: dict[str, Counter] = defaultdict(Counter)
    order_months: dict[str, Counter] = defaultdict(Counter)
    channel_orders: dict[str, Counter] = defaultdict(Counter)
    customer_order_counts: dict[str, Counter] = defaultdict(Counter)
    product_line_counts: dict[str, Counter] = defaultdict(Counter)
    campaign_attributed: Counter[str] = Counter()
    weekend_orders: Counter[str] = Counter()
    cross_month_refunds = 0
    completed_gross = 0
    completed_discounts = 0
    for order in rows["orders"]:
        workspace = order["workspace_id"]
        ordered_at = datetime.fromisoformat(order["ordered_at"])
        assert start <= ordered_at < end and ordered_at.utcoffset().total_seconds() == 0, f"{order['id']}: order date outside UTC window"
        assert order["status"] in {"completed", "cancelled"} and order["currency"] == "USD"
        assert customers[order["customer_id"]]["workspace_id"] == workspace
        assert datetime.fromisoformat(customers[order["customer_id"]]["created_at"]) <= ordered_at
        assert channels[order["channel_id"]]["workspace_id"] == workspace
        if order["campaign_id"]:
            campaign = campaigns[order["campaign_id"]]
            assert campaign["workspace_id"] == workspace
            assert datetime.fromisoformat(campaign["starts_at"]) <= ordered_at < datetime.fromisoformat(campaign["ends_at"])
        assert int(order["discount_cents"]) >= 0
        order_statuses[workspace][order["status"]] += 1
        order_months[workspace][order["ordered_at"][:7]] += 1
        channel_orders[workspace][channels[order["channel_id"]]["name"]] += 1
        customer_order_counts[workspace][order["customer_id"]] += 1
        campaign_attributed[workspace] += bool(order["campaign_id"])
        weekend_orders[workspace] += ordered_at.weekday() >= 5

    for line in rows["order_lines"]:
        order = orders[line["order_id"]]
        assert line["workspace_id"] == order["workspace_id"] == products[line["product_id"]]["workspace_id"]
        quantity, price, discount = (int(line[field]) for field in ("quantity", "unit_price_cents", "discount_cents"))
        gross = quantity * price
        assert quantity > 0 and price > 0 and 0 <= discount < gross
        order_discounts[order["id"]] += discount
        order_line_count[order["id"]] += 1
        product_line_counts[order["workspace_id"]][line["product_id"]] += 1
        if order["status"] == "completed":
            completed_gross += gross
            completed_discounts += discount
            workspace_amounts[order["workspace_id"]]["gross_sales_cents"] += gross
            workspace_amounts[order["workspace_id"]]["discounts_cents"] += discount
    assert all(count > 0 for count in order_line_count.values())
    assert len(order_line_count) == len(orders), "order with no lines"
    assert all(order_discounts[order_id] == int(order["discount_cents"]) for order_id, order in orders.items()), "order/line discount mismatch"

    for refund in rows["refunds"]:
        line = lines[refund["order_line_id"]]
        order = orders[line["order_id"]]
        assert refund["workspace_id"] == line["workspace_id"] == order["workspace_id"]
        assert order["status"] == "completed", "cancelled order refunded"
        refunded_at = datetime.fromisoformat(refund["refunded_at"])
        assert datetime.fromisoformat(order["ordered_at"]) < refunded_at < end and refunded_at.utcoffset().total_seconds() == 0
        amount = int(refund["amount_cents"])
        assert amount > 0
        refund_total[line["id"]] += amount
        workspace_amounts[refund["workspace_id"]]["refunds_cents"] += amount
        cross_month_refunds += refunded_at.strftime("%Y-%m") != order["ordered_at"][:7]
    for line_id, amount in refund_total.items():
        line = lines[line_id]
        assert amount <= int(line["quantity"]) * int(line["unit_price_cents"]) - int(line["discount_cents"]), "refund exceeds discounted sale"

    stockout_starts: dict[str, datetime] = {}
    stockout_periods: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    for event in sorted(rows["inventory_events"], key=lambda row: row["event_at"]):
        product_id = event["product_id"]
        assert products[product_id]["workspace_id"] == event["workspace_id"]
        when = datetime.fromisoformat(event["event_at"])
        if event["event_type"] == "stockout_start":
            assert product_id not in stockout_starts and int(event["quantity"]) == 0
            stockout_starts[product_id] = when
        elif event["event_type"] == "restocked":
            assert product_id in stockout_starts and int(event["quantity"]) > 0
            stockout_periods[product_id].append((stockout_starts.pop(product_id), when))
        else:
            raise AssertionError(f"Unknown inventory event: {event['event_type']}")
    assert not stockout_starts, "unclosed stockout"
    for line in rows["order_lines"]:
        when = datetime.fromisoformat(orders[line["order_id"]]["ordered_at"])
        assert all(not (first <= when < last) for first, last in stockout_periods.get(line["product_id"], [])), "stockout item sold"

    for event in rows["campaign_events"]:
        campaign = campaigns[event["campaign_id"]]
        assert event["workspace_id"] == campaign["workspace_id"]
        json.loads(event["details_json"])

    net_revenue = completed_gross - completed_discounts - sum(refund_total.values())
    assert net_revenue >= 0
    if manifest["profile"] == "full":
        assert cross_month_refunds > 0, "expected delayed refunds crossing month boundaries"
    for amounts in workspace_amounts.values():
        amounts["net_revenue_cents"] = amounts["gross_sales_cents"] - amounts["discounts_cents"] - amounts["refunds_cents"]
    return {
        "dataset": manifest["dataset"],
        "profile": manifest["profile"],
        "reference_date": manifest["reference_date"],
        "counts": manifest["counts"],
        "completed_gross_cents": completed_gross,
        "completed_discounts_cents": completed_discounts,
        "refunds_cents": sum(refund_total.values()),
        "net_revenue_cents": net_revenue,
        "workspace_amounts": {workspace: dict(amounts) for workspace, amounts in workspace_amounts.items()},
        "order_statuses": {workspace: dict(statuses) for workspace, statuses in order_statuses.items()},
        "order_months": {workspace: dict(months) for workspace, months in order_months.items()},
        "channel_orders": {workspace: dict(channels) for workspace, channels in channel_orders.items()},
        "cross_month_refunds": cross_month_refunds,
        "stockout_periods": sum(len(periods) for periods in stockout_periods.values()),
        "distribution": {
            workspace: {
                "weekend_orders": weekend_orders[workspace],
                "campaign_attributed_orders": campaign_attributed[workspace],
                "top_10_percent_customers_order_share": round(sum(count for _, count in customer_order_counts[workspace].most_common(max(1, len(customer_order_counts[workspace]) // 10))) / sum(customer_order_counts[workspace].values()), 4),
                "top_10_percent_products_line_share": round(sum(count for _, count in product_line_counts[workspace].most_common(max(1, len(product_line_counts[workspace]) // 10))) / sum(product_line_counts[workspace].values()), 4),
            }
            for workspace in sorted(workspace_ids)
        },
        "checks": ["referential_integrity", "workspace_isolation", "money_reconciliation", "date_and_refund_ordering", "stockouts", "manifest_hashes"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, help="Optional machine-readable QA report path")
    args = parser.parse_args()
    report = validate(args.directory)
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
