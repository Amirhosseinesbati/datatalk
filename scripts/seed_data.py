"""Deterministic Northstar Supply demo data generator.

The generated CSVs are the public demo dataset. Evaluation answers and the
planted event rules live separately under evals/ and are never loaded by the app.
"""

from __future__ import annotations

import argparse
import bisect
import calendar
import csv
import hashlib
import json
import random
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path


UTC = timezone.utc
DEFAULT_REFERENCE_DATE = date(2026, 9, 28)
DEFAULT_SEED = 4104
NORTHSTAR = "ws-northstar"
EASTWIND = "ws-eastwind"

HEADERS = {
    "workspaces": ["id", "name"],
    "customers": ["id", "workspace_id", "name", "email", "created_at"],
    "products": ["id", "workspace_id", "name", "category", "cost_cents"],
    "channels": ["id", "workspace_id", "name"],
    "campaigns": ["id", "workspace_id", "name", "starts_at", "ends_at"],
    "campaign_events": ["id", "workspace_id", "campaign_id", "event_at", "event_type", "details_json"],
    "inventory_events": ["id", "workspace_id", "product_id", "event_at", "event_type", "quantity"],
    "orders": ["id", "workspace_id", "customer_id", "channel_id", "campaign_id", "ordered_at", "status", "currency", "discount_cents"],
    "order_lines": ["id", "workspace_id", "order_id", "product_id", "quantity", "unit_price_cents", "discount_cents"],
    "refunds": ["id", "workspace_id", "order_line_id", "refunded_at", "amount_cents", "reason"],
}

CATEGORY_ITEMS = {
    "Office Supplies": ["Notebook", "Binder", "Desk Pad", "Marker Set", "Pen Pack", "Folder", "Label Roll", "Paper Ream", "Stapler", "Clip Box", "Desk Organizer", "Index Card", "Whiteboard", "Tape Dispenser", "Envelope Pack", "Highlighter", "File Tray", "Punch", "Planner", "Clipboard"],
    "Cleaning": ["Surface Spray", "Mop Head", "Microfiber Cloth", "Hand Soap", "Sanitizer", "Trash Liner", "Floor Cleaner", "Glass Cleaner", "Paper Towel", "Brush Set", "Disinfectant Wipe", "Broom", "Dustpan", "Glove Pack", "Sponge", "Bucket", "Detergent", "Air Freshener", "Scrub Pad", "Cleaning Cart"],
    "Breakroom": ["Coffee Beans", "Tea Assortment", "Cup Sleeve", "Paper Cup", "Sugar Sachet", "Water Filter", "Snack Box", "Napkin Pack", "Stirrer", "Coffee Filter", "Kettle", "Mug", "Pitcher", "Plate Pack", "Cutlery Set", "Milk Frother", "Food Container", "Coffee Grinder", "Bottle", "Dish Soap"],
    "Shipping": ["Parcel Box", "Padded Mailer", "Packing Tape", "Shipping Label", "Bubble Wrap", "Stretch Film", "Pallet Wrap", "Document Sleeve", "Postal Scale", "Carton Knife", "Strapping Roll", "Void Fill", "Pallet Label", "Seal Pack", "Corrugated Sheet", "Tube Mailer", "Tape Gun", "Shipping Tag", "Return Pouch", "Label Printer"],
    "Safety": ["Safety Glasses", "Hi Vis Vest", "Ear Plug", "First Aid Kit", "Hard Hat", "Respirator", "Warning Sign", "Barrier Tape", "Knee Pad", "Face Shield", "Fire Blanket", "Safety Cone", "Work Glove", "Eye Wash", "Spill Kit", "Dust Mask", "Reflective Tape", "Harness", "Thermal Glove", "Emergency Light"],
    "Electronics": ["USB Hub", "Power Strip", "Monitor Arm", "Webcam", "Keyboard", "Mouse", "Charging Cable", "Headset", "Desk Charger", "Portable Drive", "Cable Organizer", "Network Switch", "Docking Station", "Desk Speaker", "Surge Protector", "Adapter", "LED Lamp", "Battery Pack", "Ethernet Cable", "Label Scanner"],
    "Furniture": ["Task Chair", "Standing Desk", "Bookcase", "Drawer Unit", "Meeting Table", "Shelf", "Footrest", "Visitor Chair", "Filing Cabinet", "Desk Riser", "Coat Stand", "Storage Bench", "Side Table", "Monitor Stand", "Cabinet", "Partition", "Desk Frame", "Stool", "Wall Shelf", "Storage Cart"],
    "Facility": ["Door Mat", "Wall Clock", "LED Bulb", "Cable Tray", "Key Cabinet", "Extension Cord", "Floor Sign", "Notice Board", "Waste Bin", "Wall Hook", "Umbrella Stand", "Room Sign", "Thermostat", "Door Stop", "Air Filter", "Light Panel", "Fan", "Dehumidifier", "Storage Rack", "Window Shade"],
    "Tools": ["Screwdriver Set", "Measuring Tape", "Utility Knife", "Pliers", "Drill Bit", "Tool Bag", "Level", "Hex Key", "Wrench", "Hammer", "Cable Tester", "Fastener Kit", "Saw", "Clamp", "Socket Set", "Work Light", "Wire Cutter", "Drill", "Stud Finder", "Ladder"],
    "Packaging": ["Gift Box", "Tissue Paper", "Paper Bag", "Cotton Twine", "Seal Sticker", "Retail Sleeve", "Display Carton", "Product Insert", "Ribbon Roll", "Sample Pouch", "Kraft Wrap", "Jar Label", "Hang Tag", "Bottle Box", "Protective Foam", "Product Tray", "Mailer Insert", "Tamper Seal", "Wrap Sheet", "Retail Label"],
}

FIRST_NAMES = "Avery Jordan Morgan Casey Taylor Riley Alex Cameron Quinn Rowan Jamie Drew Parker Reese Blair Elliott Sage Sydney Devon Harper".split()
LAST_NAMES = "Mason Ellis Brooks Turner Hayes Parker Chen Patel Brooks Rivera Morgan Reed Foster Bennett Price Cole Wright Kelly Stone Gray".split()
CHANNEL_NAMES = ["Direct Web", "Marketplace", "Wholesale", "Field Sales", "Partner Portal", "Mobile App"]
CHANNEL_WEIGHTS = [31, 22, 18, 14, 9, 6]


def subtract_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, zero_month = divmod(month_index, 12)
    month = zero_month + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def stamp(value: datetime | date) -> str:
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, time.min, UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds")


class TableWriter:
    def __init__(self, output: Path):
        output.mkdir(parents=True, exist_ok=True)
        self.output = output
        self.files = {}
        self.writers = {}
        self.counts = Counter()
        for table, columns in HEADERS.items():
            handle = (output / f"{table}.csv").open("w", encoding="utf-8", newline="")
            writer = csv.DictWriter(handle, columns, extrasaction="raise", lineterminator="\n")
            writer.writeheader()
            self.files[table] = handle
            self.writers[table] = writer

    def write(self, table: str, row: dict) -> None:
        self.writers[table].writerow(row)
        self.counts[table] += 1

    def close(self) -> None:
        for handle in self.files.values():
            handle.close()


def make_campaigns(start: date, end: date, writer: TableWriter) -> list[tuple[str, date, date]]:
    length = (end - start).days
    schedule = [
        ("Spring Workspace Refresh", 0.12, 0.18),
        ("Autumn Procurement Week", 0.39, 0.43),
        ("Winter Operations Drive", 0.57, 0.64),
        ("Summer Relay", 0.85, 0.91),
    ]
    campaigns = []
    for index, (name, begin, finish) in enumerate(schedule, 1):
        first = start + timedelta(days=round(length * begin))
        last = start + timedelta(days=round(length * finish))
        campaign_id = f"ns-camp-{index:02d}"
        writer.write("campaigns", {"id": campaign_id, "workspace_id": NORTHSTAR, "name": name, "starts_at": stamp(first), "ends_at": stamp(last)})
        campaigns.append((campaign_id, first, last))
        for event_no, (event_at, event_type, details) in enumerate(
            [
                (first, "launched", {"channel": "Direct Web", "audience_count": 820}),
                (first + timedelta(days=2), "email_sent", {"channel": "Partner Portal", "audience_count": 430}),
                (last, "ended", {"channel": "all"}),
            ], 1
        ):
            writer.write("campaign_events", {"id": f"ns-ce-{index:02d}-{event_no}", "workspace_id": NORTHSTAR, "campaign_id": campaign_id, "event_at": stamp(event_at), "event_type": event_type, "details_json": json.dumps(details, separators=(",", ":"))})
    return campaigns


def make_stockouts(start: date, end: date, product_ids: list[str], writer: TableWriter, rng: random.Random) -> dict[str, list[tuple[date, date]]]:
    stockouts: dict[str, list[tuple[date, date]]] = {}
    span = (end - start).days
    for index in range(1, 17):
        product_id = product_ids[(index * 3) % min(len(product_ids), 55)]
        first = start + timedelta(days=round(span * (0.08 + 0.052 * index)))
        last = min(end, first + timedelta(days=rng.randint(4, 11)))
        stockouts.setdefault(product_id, []).append((first, last))
        writer.write("inventory_events", {"id": f"ns-ie-{index:03d}-start", "workspace_id": NORTHSTAR, "product_id": product_id, "event_at": stamp(first), "event_type": "stockout_start", "quantity": 0})
        writer.write("inventory_events", {"id": f"ns-ie-{index:03d}-end", "workspace_id": NORTHSTAR, "product_id": product_id, "event_at": stamp(last), "event_type": "restocked", "quantity": rng.randint(80, 240)})
    return stockouts


def order_line_counts(total_orders: int, target_lines: int, rng: random.Random) -> list[int]:
    counts = [1] * total_orders
    remaining = target_lines - total_orders
    while remaining:
        index = rng.randrange(total_orders)
        if counts[index] < 5:
            counts[index] += 1
            remaining -= 1
    rng.shuffle(counts)
    return counts


def make_order_days(start: date, end: date, count: int, campaigns: list[tuple[str, date, date]], rng: random.Random) -> list[date]:
    days = [start + timedelta(days=offset) for offset in range((end - start).days)]
    month_factor = {1: 0.86, 2: 0.91, 3: 1.00, 4: 1.04, 5: 1.00, 6: 1.01, 7: 1.05, 8: 1.00, 9: 1.08, 10: 1.17, 11: 1.43, 12: 1.33}
    weights = []
    for day in days:
        weight = month_factor[day.month] * (0.72 if day.weekday() >= 5 else 1.12)
        if any(first <= day < last for _, first, last in campaigns):
            weight *= 1.29
        weights.append(weight)
    selected = rng.choices(days, weights, k=count)
    selected.sort()
    return selected


def generate(profile: str, output: Path, seed: int, reference_date: date) -> dict:
    rng = random.Random(seed)
    start = subtract_months(reference_date, 18)
    end = reference_date
    full = profile == "full"
    n_orders, n_lines, n_customers, n_products = (50_000, 120_000, 5_000, 200) if full else (1_000, 2_400, 300, 60)
    writer = TableWriter(output)
    writer.write("workspaces", {"id": NORTHSTAR, "name": "Northstar Supply — Synthetic Demo"})
    writer.write("workspaces", {"id": EASTWIND, "name": "Eastwind Fixture — Isolation Test"})

    products: list[tuple[str, int]] = []
    for number, (category, names) in enumerate(CATEGORY_ITEMS.items()):
        for offset, name in enumerate(names):
            if len(products) >= n_products:
                break
            index = len(products) + 1
            unit_price = rng.randint(800, 4_800) if number < 6 else rng.randint(2_500, 46_000)
            cost = round(unit_price * rng.uniform(0.49, 0.80))
            product_id = f"ns-p-{index:03d}"
            products.append((product_id, unit_price))
            writer.write("products", {"id": product_id, "workspace_id": NORTHSTAR, "name": f"Northstar {name} {['Core', 'Plus', 'Pro'][offset % 3]}", "category": category, "cost_cents": cost})
    product_ids = [product_id for product_id, _ in products]
    product_price = dict(products)
    product_weights = [1 / ((index + 2) ** 0.78) for index in range(n_products)]
    cumulative = []
    total_weight = 0.0
    for weight in product_weights:
        total_weight += weight
        cumulative.append(total_weight)

    for index, name in enumerate(CHANNEL_NAMES, 1):
        writer.write("channels", {"id": f"ns-ch-{index:02d}", "workspace_id": NORTHSTAR, "name": name})
    campaigns = make_campaigns(start, end, writer)
    stockouts = make_stockouts(start, end, product_ids, writer, rng)

    order_days = make_order_days(start, end, n_orders, campaigns, rng)
    line_counts = order_line_counts(n_orders, n_lines, rng)
    forced_customer_ids = list(range(1, n_customers + 1))
    rng.shuffle(forced_customer_ids)
    forced_order_positions = set(round(index * (n_orders - 1) / (n_customers - 1)) for index in range(n_customers))
    customer_first: dict[int, datetime] = {}
    forced_index = 0
    line_index = 0
    refund_index = 0
    completed_count = 0
    cancelled_count = 0
    channel_ids = [f"ns-ch-{index:02d}" for index in range(1, 7)]
    for order_no, (day, line_count) in enumerate(zip(order_days, line_counts, strict=True), 1):
        ordered_at = datetime.combine(day, time.min, UTC) + timedelta(hours=rng.randint(7, 19), minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
        if order_no - 1 in forced_order_positions:
            customer_no = forced_customer_ids[forced_index]
            forced_index += 1
        else:
            customer_no = min(n_customers, int(rng.paretovariate(1.15) * 110))
            if rng.random() < 0.26:
                customer_no = rng.randint(1, n_customers)
        customer_first[customer_no] = min(customer_first.get(customer_no, ordered_at), ordered_at)
        order_id = f"ns-o-{order_no:06d}"
        status = "cancelled" if rng.random() < 0.046 else "completed"
        completed_count += status == "completed"
        cancelled_count += status == "cancelled"
        channel_id = rng.choices(channel_ids, CHANNEL_WEIGHTS, k=1)[0]
        active_campaigns = [campaign_id for campaign_id, first, last in campaigns if first <= day < last]
        campaign_id = active_campaigns[0] if active_campaigns and rng.random() < 0.34 else ""
        order_discount = 0
        selected_products: set[str] = set()
        for _ in range(line_count):
            while True:
                candidate = product_ids[bisect.bisect_left(cumulative, rng.random() * total_weight)]
                if candidate in selected_products or any(first <= day < last for first, last in stockouts.get(candidate, [])):
                    continue
                selected_products.add(candidate)
                break
            line_index += 1
            quantity = rng.choices([1, 2, 3, 4, 5], [59, 26, 10, 4, 1], k=1)[0]
            price = product_price[candidate]
            gross = quantity * price
            discount_rate = rng.choice([0, 0, 0, 0, 0.03, 0.05, 0.08])
            if campaign_id:
                discount_rate = rng.choice([0.08, 0.10, 0.12, 0.15, 0.18])
            discount = round(gross * discount_rate)
            order_discount += discount
            line_id = f"ns-l-{line_index:07d}"
            writer.write("order_lines", {"id": line_id, "workspace_id": NORTHSTAR, "order_id": order_id, "product_id": candidate, "quantity": quantity, "unit_price_cents": price, "discount_cents": discount})
            if status == "completed" and rng.random() < 0.032:
                delay = rng.randint(2, 63)
                refunded_at = ordered_at + timedelta(days=delay, hours=rng.randint(0, 12))
                if refunded_at.date() < end:
                    refundable = gross - discount
                    amount = refundable if rng.random() < 0.58 else max(1, round(refundable * rng.uniform(0.15, 0.82)))
                    refund_index += 1
                    writer.write("refunds", {"id": f"ns-r-{refund_index:06d}", "workspace_id": NORTHSTAR, "order_line_id": line_id, "refunded_at": stamp(refunded_at), "amount_cents": amount, "reason": rng.choice(["damaged", "customer_return", "late_delivery", "quality_issue"])})
        writer.write("orders", {"id": order_id, "workspace_id": NORTHSTAR, "customer_id": f"ns-c-{customer_no:05d}", "channel_id": channel_id, "campaign_id": campaign_id, "ordered_at": stamp(ordered_at), "status": status, "currency": "USD", "discount_cents": order_discount})

    if len(customer_first) != n_customers:
        raise AssertionError(f"Only {len(customer_first)} of {n_customers} customers received orders")
    for index in range(1, n_customers + 1):
        first_order = customer_first[index]
        created = max(datetime.combine(start - timedelta(days=365), time.min, UTC), first_order - timedelta(days=rng.randint(0, 145), hours=rng.randint(0, 23)))
        writer.write("customers", {"id": f"ns-c-{index:05d}", "workspace_id": NORTHSTAR, "name": f"{FIRST_NAMES[(index * 7) % len(FIRST_NAMES)]} {LAST_NAMES[(index * 13) % len(LAST_NAMES)]}", "email": f"customer{index:05d}@northstar.example", "created_at": stamp(created)})

    # Small separate workspace makes row-isolation tests observable.
    for index in range(1, 13):
        writer.write("customers", {"id": f"ew-c-{index:03d}", "workspace_id": EASTWIND, "name": f"Eastwind Buyer {index:03d}", "email": f"buyer{index:03d}@eastwind.example", "created_at": stamp(start - timedelta(days=12))})
    for index in range(1, 7):
        writer.write("products", {"id": f"ew-p-{index:03d}", "workspace_id": EASTWIND, "name": f"Eastwind Fixture Item {index}", "category": "Fixture", "cost_cents": 300 + index * 65})
    for index, name in enumerate(["Eastwind Direct", "Eastwind Partner"], 1):
        writer.write("channels", {"id": f"ew-ch-{index:02d}", "workspace_id": EASTWIND, "name": name})
    for index in range(1, 31):
        order_id = f"ew-o-{index:03d}"
        ordered_at = datetime.combine(start + timedelta(days=(index * 17) % max(1, (end - start).days)), time(11), UTC)
        status = "cancelled" if index % 11 == 0 else "completed"
        discount_sum = 0
        for line_no in range(1, 3):
            line_id = f"ew-l-{index:03d}-{line_no}"
            price = 950 + 125 * line_no
            discount = 50 if index % 3 == 0 else 0
            discount_sum += discount
            writer.write("order_lines", {"id": line_id, "workspace_id": EASTWIND, "order_id": order_id, "product_id": f"ew-p-{(index + line_no) % 6 + 1:03d}", "quantity": 1, "unit_price_cents": price, "discount_cents": discount})
            if status == "completed" and index % 10 == 0 and line_no == 1 and ordered_at.date() + timedelta(days=7) < end:
                writer.write("refunds", {"id": f"ew-r-{index:03d}", "workspace_id": EASTWIND, "order_line_id": line_id, "refunded_at": stamp(ordered_at + timedelta(days=7)), "amount_cents": 400, "reason": "customer_return"})
        writer.write("orders", {"id": order_id, "workspace_id": EASTWIND, "customer_id": f"ew-c-{index % 12 + 1:03d}", "channel_id": f"ew-ch-{index % 2 + 1:02d}", "campaign_id": "", "ordered_at": stamp(ordered_at), "status": status, "currency": "USD", "discount_cents": discount_sum})

    writer.close()
    file_hashes = {}
    for table in HEADERS:
        path = output / f"{table}.csv"
        file_hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "dataset": "Synthetic demo dataset — Northstar Supply",
        "profile": profile,
        "seed": seed,
        "reference_date": reference_date.isoformat(),
        "start_at": stamp(start),
        "end_at_exclusive": stamp(end),
        "timezone": "UTC",
        "currency": "USD",
        "counts": dict(writer.counts),
        "counts_by_workspace": {
            NORTHSTAR: {"customers": n_customers, "products": n_products, "channels": 6, "orders": n_orders, "order_lines": n_lines, "completed_orders": completed_count, "cancelled_orders": cancelled_count, "refunds": refund_index},
            EASTWIND: {"customers": 12, "products": 6, "channels": 2, "orders": 30, "order_lines": 60},
        },
        "files_sha256": file_hashes,
        "notes": ["All amounts are integer USD cents", "UTC half-open date intervals", "orders.discount_cents is the sum of line discounts, not an additional discount", "All rows and company names are fictional"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["fast", "full"], default="fast")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--reference-date", type=date.fromisoformat, default=DEFAULT_REFERENCE_DATE)
    args = parser.parse_args()
    output = args.output or Path(__file__).resolve().parents[1] / "data" / "generated" / args.profile
    manifest = generate(args.profile, output, args.seed, args.reference_date)
    print(json.dumps({"output": str(output), "counts": manifest["counts"], "reference_date": manifest["reference_date"]}, indent=2))


if __name__ == "__main__":
    main()
