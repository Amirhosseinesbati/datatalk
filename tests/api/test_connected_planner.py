"""CONNECTED planning contract tests run entirely with an in-process model fake."""

from datetime import date
from types import SimpleNamespace

import langchain_openai
import pytest

import datatalk.planner as planner_module
from datatalk.planner import ConnectedPlanner
from datatalk.schemas import PlanningDecision


def test_connected_planner_requires_key_without_calling_model(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required"):
        ConnectedPlanner("test-model").plan("Net revenue in February 2026", date(2026, 9, 27))


def test_connected_planner_validates_structured_model_output(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")

    class FakeModel:
        def __init__(self, **kwargs):
            assert kwargs["model"] == "test-model"
            assert kwargs["max_tokens"] == 900

        def with_structured_output(self, schema, method, include_raw):
            assert schema is PlanningDecision
            assert method == "json_schema"
            assert include_raw is True
            return self

        def invoke(self, messages):
            assert len(messages) == 2
            return {
                "raw": SimpleNamespace(usage_metadata={"input_tokens": 300, "output_tokens": 40, "total_tokens": 340}),
                "parsed": {"kind": "plan", "plan": {"metrics": ["net_revenue"], "start_date": "2026-02-01", "end_date": "2026-03-01"}},
                "parsing_error": None,
            }

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeModel)
    monkeypatch.setattr(planner_module, "get_settings", lambda: SimpleNamespace(datatalk_model_input_usd_per_million=1.0, datatalk_model_output_usd_per_million=2.0))
    planner = ConnectedPlanner("test-model")
    decision = planner.plan("Net revenue in February 2026", date(2026, 9, 27))
    assert decision.kind == "plan"
    assert decision.plan is not None
    assert decision.plan.start_date == date(2026, 2, 1)
    assert planner.last_usage == {"model_id": "test-model", "input_tokens": 300, "output_tokens": 40, "total_tokens": 340, "usage_status": "known", "cost_usd": 0.00038, "cost_status": "known"}


def test_connected_planner_propagates_model_failure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")

    class FailingModel:
        def __init__(self, **kwargs):
            pass

        def with_structured_output(self, schema, method, include_raw):
            return self

        def invoke(self, messages):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FailingModel)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        ConnectedPlanner("test-model").plan("Net revenue in February 2026", date(2026, 9, 27))
