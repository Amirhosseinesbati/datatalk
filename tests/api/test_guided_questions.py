"""User-facing starter/builder wording must preserve the chosen analytical scope."""

from datetime import date

import pytest
from datatalk.planner import DemoPlanner


@pytest.mark.parametrize(
    ("question", "metric", "dimension", "start", "end", "comparison"),
    [
        (
            "Show net revenue by category last month.",
            "net_revenue",
            "category",
            "2026-09-01",
            "2026-10-01",
            "none",
        ),
        (
            "Show refunds by month this year.",
            "refunds",
            "month",
            "2026-01-01",
            "2027-01-01",
            "none",
        ),
        (
            "Compare completed orders by channel last month with the previous period.",
            "completed_orders",
            "channel",
            "2026-09-01",
            "2026-10-01",
            "previous_period",
        ),
        (
            "Show average order value last year.",
            "average_order_value",
            None,
            "2025-01-01",
            "2026-01-01",
            "none",
        ),
        (
            "Show gross sales by customer last month.",
            "gross_sales",
            "customer",
            "2026-09-01",
            "2026-10-01",
            "none",
        ),
        (
            "Show returning customers by category last month.",
            "returning_customers",
            "category",
            "2026-09-01",
            "2026-10-01",
            "none",
        ),
    ],
)
def test_guided_question_preserves_scope(
    question, metric, dimension, start, end, comparison
):
    decision = DemoPlanner().plan(question, date(2026, 10, 6))
    assert decision.kind == "plan"
    assert decision.plan is not None
    assert decision.plan.metrics == [metric]
    assert decision.plan.dimensions == ([dimension] if dimension else [])
    assert decision.plan.start_date.isoformat() == start
    assert decision.plan.end_date.isoformat() == end
    assert decision.plan.comparison == comparison
