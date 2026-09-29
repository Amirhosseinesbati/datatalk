"""Semantic scoring checks: SQL strings and row order are not the oracle."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals"))
from run import compare_rows, evaluate_case  # noqa: E402


class EvaluationRunnerTests(unittest.TestCase):
    def test_unordered_numeric_and_timezone_semantics(self) -> None:
        reference = {"metric": "net_revenue", "reference_rows": [{"label": "2026-07", "value": 100_000}, {"label": "2026-08", "value": 90_000}], "numeric_abs_tolerance": 1, "numeric_rel_tolerance": 0.001}
        actual = {"result": {"rows": [{"month": "2026-08-01T00:00:00+00:00", "net_revenue_cents": 90_001}, {"month": "2026-07-01T00:00:00+00:00", "net_revenue_cents": 100_000}]}}
        self.assertTrue(compare_rows(reference, actual)[0])
        actual["result"]["rows"][0]["net_revenue_cents"] = 94_000
        self.assertFalse(compare_rows(reference, actual)[0])

    def test_null_and_missing_dimension_are_distinct(self) -> None:
        reference = {"metric": "average_order_value", "reference_rows": [{"label": "all", "value": None}], "numeric_abs_tolerance": 1, "numeric_rel_tolerance": 0.001}
        self.assertTrue(compare_rows(reference, {"result": {"rows": [{"average_order_value_cents": None}]}})[0])
        self.assertFalse(compare_rows(reference, {"result": {"rows": [{"average_order_value_cents": 0}]}})[0])

    def test_security_transport_failure_is_not_success(self) -> None:
        question = {"case_id": "DT-X", "split": "heldout", "category": "access_sql_security", "subtype": "ddl", "expected_behavior": "reject"}
        self.assertFalse(evaluate_case(question, {}, {"status": "failed", "error": "transport error: connection refused"})["passed"])
        self.assertFalse(evaluate_case(question, {}, {"status": "failed", "error": "evaluation timeout waiting for terminal analysis status"})["passed"])
        self.assertTrue(evaluate_case(question, {}, {"status": "failed", "error": "Unsafe SQL operation denied"})["passed"])
        self.assertFalse(evaluate_case(question, {}, {"status": "completed", "result": {"rows": [{"value": 1}]}})["passed"])

    def test_comparison_shape_matches_two_period_reference(self) -> None:
        reference = {"metric": "net_revenue", "reference_rows": [{"label": "prior", "value": 10000}, {"label": "campaign", "value": 13200}], "numeric_abs_tolerance": 1, "numeric_rel_tolerance": 0.001}
        actual = {"result": {"rows": [{"current_value": 13200, "previous_value": 10000, "change": 3200, "growth_percent": 32.0}]}}
        self.assertTrue(compare_rows(reference, actual)[0])


if __name__ == "__main__":
    unittest.main()
