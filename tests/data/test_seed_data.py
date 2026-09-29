"""Independent synthetic-data and evaluation-fixture invariants."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from seed_data import DEFAULT_REFERENCE_DATE, DEFAULT_SEED, generate  # noqa: E402
from validate_data import validate  # noqa: E402


class SyntheticDataTests(unittest.TestCase):
    def test_fast_seed_is_deterministic_and_workspace_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first"
            second = Path(temp) / "second"
            manifest_a = generate("fast", first, DEFAULT_SEED, DEFAULT_REFERENCE_DATE)
            manifest_b = generate("fast", second, DEFAULT_SEED, DEFAULT_REFERENCE_DATE)
            self.assertEqual(manifest_a["files_sha256"], manifest_b["files_sha256"])
            self.assertEqual(manifest_a["counts_by_workspace"]["ws-northstar"]["orders"], 1_000)
            self.assertEqual(manifest_a["counts_by_workspace"]["ws-northstar"]["order_lines"], 2_400)
            report = validate(first)
            self.assertGreater(report["net_revenue_cents"], 0)
            self.assertIn("workspace_isolation", report["checks"])

    def test_full_seed_contract_and_reconciliation(self) -> None:
        dataset = ROOT / "data" / "generated" / "full"
        if not (dataset / "manifest.json").exists():
            with tempfile.TemporaryDirectory() as temp:
                dataset = Path(temp) / "full"
                generate("full", dataset, DEFAULT_SEED, DEFAULT_REFERENCE_DATE)
                self._assert_full(dataset)
        else:
            self._assert_full(dataset)

    def _assert_full(self, dataset: Path) -> None:
        report = validate(dataset)
        manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
        northstar = manifest["counts_by_workspace"]["ws-northstar"]
        self.assertEqual((northstar["orders"], northstar["order_lines"], northstar["customers"], northstar["products"], northstar["channels"]), (50_000, 120_000, 5_000, 200, 6))
        self.assertEqual(northstar["completed_orders"] + northstar["cancelled_orders"], 50_000)
        self.assertEqual(report["completed_gross_cents"] - report["completed_discounts_cents"] - report["refunds_cents"], report["net_revenue_cents"])

    def test_metric_edge_case_fixture(self) -> None:
        fixture = json.loads((ROOT / "fixtures" / "metric_invariants.json").read_text(encoding="utf-8"))
        orders = {row["id"]: row for row in fixture["orders"]}
        lines = {row["id"]: row for row in fixture["order_lines"]}
        monthly: dict[str, Counter] = {}
        order_ids: dict[str, set[str]] = {}
        for line in lines.values():
            order = orders[line["order_id"]]
            if order["status"] != "completed":
                continue
            month = order["ordered_at"][:7]
            monthly.setdefault(month, Counter())
            order_ids.setdefault(month, set()).add(order["id"])
            monthly[month]["gross_sales_cents"] += line["quantity"] * line["unit_price_cents"]
            monthly[month]["discounts_cents"] += line["discount_cents"]
        for refund in fixture["refunds"]:
            month = refund["refunded_at"][:7]
            monthly.setdefault(month, Counter())["refunds_cents"] += refund["amount_cents"]
        for month, expected in fixture["expected_months"].items():
            values = monthly.get(month, Counter())
            gross = values["gross_sales_cents"]
            discounts = values["discounts_cents"]
            refunds = values["refunds_cents"]
            count = len(order_ids.get(month, set()))
            observed = {"gross_sales_cents": gross, "discounts_cents": discounts, "refunds_cents": refunds, "net_revenue_cents": gross - discounts - refunds, "completed_orders": count, "average_order_value_cents": (gross - discounts) / count if count else None}
            self.assertEqual(observed, expected, month)
        self.assertEqual(sum(line["discount_cents"] for line in lines.values() if orders[line["order_id"]]["status"] == "completed"), orders["A"]["discount_cents"] + orders["C"]["discount_cents"])
        self.assertEqual(sum(refund["amount_cents"] for refund in fixture["refunds"]), 6_000)

    def test_eval_reference_is_private_and_complete(self) -> None:
        public = [json.loads(line) for line in (ROOT / "evals" / "questions.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(public), 140)
        self.assertEqual(Counter(row["split"] for row in public), {"development": 40, "heldout": 100})
        self.assertEqual(Counter(row["category"] for row in public), {"standard_aggregation": 60, "joins_cohort_refund_date": 30, "ambiguous_or_unanswerable": 20, "access_sql_security": 30})
        self.assertTrue(all("reference_rows" not in row and "reference_sql" not in row for row in public))
        private_path = ROOT / "evals" / "private" / "reference.jsonl"
        if private_path.exists():
            private = [json.loads(line) for line in private_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(private), 140)
            self.assertTrue(all(row.get("reference_rows") for row in private[:90]))
            self.assertEqual([row["case_id"] for row in public], [row["case_id"] for row in private])

    def test_import_fixtures_cover_valid_and_rejected_rows(self) -> None:
        with (ROOT / "fixtures" / "import_valid.csv").open(encoding="utf-8", newline="") as handle:
            valid = list(csv.DictReader(handle))
        with (ROOT / "fixtures" / "import_invalid.csv").open(encoding="utf-8", newline="") as handle:
            invalid = list(csv.DictReader(handle))
        self.assertEqual(len(valid), 4)
        self.assertEqual(len(invalid), 6)
        self.assertEqual(len([row for row in valid if row["order_id"] == "DEMO-501"]), 2)
        self.assertTrue(any(row["quantity"] == "0" for row in invalid))
        self.assertTrue(any(row["ordered_at"] == "not-a-date" for row in invalid))
        self.assertTrue(any(int(row["discount_cents"]) > int(row["quantity"]) * int(row["unit_price_cents"]) for row in invalid if row["quantity"].isdigit()))


if __name__ == "__main__":
    unittest.main()
