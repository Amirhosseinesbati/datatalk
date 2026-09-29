from datetime import date

from datatalk.database import make_engine
from datatalk.executor import QueryExecutor
from datatalk.graph import build_graph
from datatalk.planner import DemoPlanner
from datatalk.presentation import narrative_for
from datatalk.schemas import QueryPlan


def test_explicit_month_and_month_range_take_precedence_over_bare_year():
    planner = DemoPlanner()
    month = planner.plan("For February 2026, report net revenue.", date(2026, 9, 27))
    assert month.plan is not None
    assert (month.plan.start_date, month.plan.end_date) == (date(2026, 2, 1), date(2026, 3, 1))
    period = planner.plan("Show monthly gross sales from April 2026 through June 2026.", date(2026, 9, 27))
    assert period.plan is not None
    assert (period.plan.start_date, period.plan.end_date, period.plan.dimensions) == (date(2026, 4, 1), date(2026, 7, 1), ["month"])


def test_cohort_customer_subject_is_not_a_grouping_dimension():
    decision = DemoPlanner().plan("Of customers with their first completed order in March 2026, how many placed another completed order within 90 days?", date(2026, 9, 27))
    assert decision.plan is not None
    assert decision.plan.metrics == ["repeat_customers_90d"]
    assert decision.plan.dimensions == []


def test_returning_customer_subject_selects_only_that_metric():
    decision = DemoPlanner().plan("How many returning customers placed a completed order in June 2026?", date(2026, 9, 27))
    assert decision.plan is not None
    assert decision.plan.metrics == ["returning_customers"]
    assert decision.plan.dimensions == []


def test_product_category_followup_inherits_metric_and_date_scope():
    previous = QueryPlan(metrics=["net_revenue"], dimensions=["channel"], start_date=date(2026, 8, 1), end_date=date(2026, 9, 1))
    decision = DemoPlanner().plan("Break that down by product category", date(2026, 9, 27), previous)
    assert decision.plan is not None
    assert decision.plan.metrics == ["net_revenue"]
    assert decision.plan.dimensions == ["category"]
    assert (decision.plan.start_date, decision.plan.end_date) == (previous.start_date, previous.end_date)


def test_why_did_it_change_inherits_comparison_and_limits_causal_claim():
    previous = QueryPlan(metrics=["net_revenue"], dimensions=["channel"], start_date=date(2026, 8, 1), end_date=date(2026, 9, 1), comparison="previous_period", category="Cleaning", sort="absolute_change_desc", top_n=5)
    decision = DemoPlanner().plan("Why did it change?", date(2026, 9, 27), previous)
    assert decision.plan is not None
    plan = decision.plan
    assert (plan.metrics, plan.dimensions, plan.comparison) == (["net_revenue"], ["channel"], "previous_period")
    assert (plan.start_date, plan.end_date, plan.category) == (previous.start_date, previous.end_date, "Cleaning")
    assert (plan.sort, plan.top_n) == (previous.sort, previous.top_n)
    assert DemoPlanner().plan("Why?", date(2026, 9, 27), previous).plan.comparison == "previous_period"
    narrative, evidence = narrative_for(plan, {"columns": ["channel", "current_value", "previous_value", "change", "growth_percent"], "rows": [{"channel": "Direct Web", "current_value": 20000, "previous_value": 25000, "change": -5000, "growth_percent": -20}], "truncated": False})
    assert "-$50.00" in narrative
    assert "not evidence of causation" in narrative
    assert evidence["columns"] == ["change", "channel"]


def test_unknown_measure_clarifies_and_unsafe_sql_request_rejects():
    planner = DemoPlanner()
    assert planner.plan("Show website visitors this month", date(2026, 9, 27)).kind == "clarify"
    assert planner.plan("Create a SQL function that writes a report", date(2026, 9, 27)).kind == "reject"


def test_policy_rejection_has_explicit_error_and_no_query_result():
    engine = make_engine("sqlite://")
    try:
        state = build_graph(DemoPlanner(), QueryExecutor(engine), dialect="sqlite").invoke({
            "question": "DROP TABLE orders; then show net revenue",
            "workspace_id": "w", "reference_date": "2026-09-27", "previous_plan": None,
            "values": {},
        })
        assert state["status"] == "failed"
        assert "read-only" in state["error"]
        assert state.get("sql") is None
        assert state.get("result") is None
    finally:
        engine.dispose()
