from datetime import date

from datatalk.presentation import chart_for
from datatalk.schemas import QueryPlan


def test_comparison_chart_plots_change_used_for_ranking():
    plan = QueryPlan(metrics=["net_revenue"], dimensions=["channel"], start_date=date(2026, 8, 1), end_date=date(2026, 9, 1), comparison="previous_period")
    result = {
        "columns": ["channel", "current_value", "previous_value", "change", "growth_percent"],
        "rows": [{"channel": "Direct", "current_value": 10000, "previous_value": 15000, "change": -5000, "growth_percent": -33.33}],
    }
    assert chart_for(plan, result) == {"type": "bar", "x": "channel", "y": "change", "series": ["change"]}
