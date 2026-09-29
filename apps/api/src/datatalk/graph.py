"""Explicit bounded analysis workflow. Persisted execution records are the API source of truth."""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from .compiler import compile_plan
from .executor import QueryExecutor
from .planner import Planner
from .presentation import chart_for, narrative_for
from .schemas import QueryPlan
from .sql_policy import validate_sql


class AnalysisState(TypedDict, total=False):
    question: str
    workspace_id: str
    reference_date: str
    previous_plan: dict | None
    values: dict
    status: str
    clarification: str | None
    plan: dict | None
    sql: str | None
    params: dict | None
    source_view: str | None
    source_tables: list[str] | None
    result: dict | None
    chart: dict | None
    narrative: str | None
    evidence: dict | None
    error: str | None
    model_usage: dict | None


def build_graph(planner: Planner, executor: QueryExecutor, dialect: str = "postgresql", row_cap: int = 200, checkpointer=None):
    def scope(state: AnalysisState) -> dict:
        if not state.get("workspace_id"):
            raise ValueError("workspace scope is required")
        return {"status": "running"}

    def retrieve_catalog(state: AnalysisState) -> dict:
        # A named stage keeps catalog retrieval observable in the event log.
        return {"values": state.get("values", {})}

    def interpret(state: AnalysisState) -> dict:
        from datetime import date
        previous = QueryPlan.model_validate(state["previous_plan"]) if state.get("previous_plan") else None
        decision = planner.plan(state["question"], date.fromisoformat(state["reference_date"]), previous, state.get("values"))
        usage = getattr(planner, "last_usage", None)
        if decision.kind != "plan":
            message = decision.message or "This request cannot be answered from the approved sales catalog."
            return {"status": "clarification" if decision.kind == "clarify" else "failed", "clarification": message if decision.kind == "clarify" else None, "error": message if decision.kind == "reject" else None, "narrative": message if decision.kind == "reject" else None, "model_usage": usage}
        if decision.plan is None:
            raise ValueError("planner returned no plan")
        return {"plan": decision.plan.model_dump(mode="json"), "status": "running", "model_usage": usage}

    def route(state: AnalysisState) -> str:
        return "generate_sql" if state.get("status") == "running" else END

    def generate_sql(state: AnalysisState) -> dict:
        plan_data = state.get("plan")
        if not isinstance(plan_data, dict):
            raise ValueError("analysis plan is missing")
        plan = QueryPlan.model_validate(plan_data)
        compiled = compile_plan(plan, state["workspace_id"], dialect, row_cap)
        return {"sql": compiled.sql, "params": compiled.params, "source_view": compiled.source_view, "source_tables": compiled.source_tables}

    def validate(state: AnalysisState) -> dict:
        sql = state.get("sql")
        if not isinstance(sql, str):
            raise ValueError("compiled SQL is missing")
        validate_sql(sql, dialect="postgres" if dialect == "postgresql" else "sqlite", row_cap=row_cap + 1)
        return {}

    def execute(state: AnalysisState) -> dict:
        plan_data = state.get("plan")
        sql = state.get("sql")
        params = state.get("params")
        if not isinstance(plan_data, dict) or not isinstance(sql, str) or not isinstance(params, dict):
            raise ValueError("validated query inputs are missing")
        plan = QueryPlan.model_validate(plan_data)
        result = executor.execute(sql, params, state["workspace_id"], min(plan.top_n, row_cap))
        return {"result": result}

    def validate_result(state: AnalysisState) -> dict:
        result = state.get("result")
        if not isinstance(result, dict):
            raise ValueError("query result is missing")
        if result["row_count"] > row_cap or len(result["rows"]) != result["row_count"]:
            raise ValueError("invalid query result size")
        return {}

    def present(state: AnalysisState) -> dict:
        plan_data = state.get("plan")
        result = state.get("result")
        if not isinstance(plan_data, dict) or not isinstance(result, dict):
            raise ValueError("presentation inputs are missing")
        plan = QueryPlan.model_validate(plan_data)
        chart = chart_for(plan, result)
        narrative, evidence = narrative_for(plan, result)
        return {"chart": chart, "narrative": narrative, "evidence": evidence, "status": "completed"}

    builder = StateGraph(AnalysisState)
    builder.add_node("scope", scope)
    builder.add_node("retrieve_catalog", retrieve_catalog)
    builder.add_node("interpret", interpret)
    builder.add_node("generate_sql", generate_sql)
    builder.add_node("validate_sql", validate)
    builder.add_node("execute", execute)
    builder.add_node("validate_result", validate_result)
    builder.add_node("build_chart_narrative", present)
    builder.add_edge(START, "scope")
    builder.add_edge("scope", "retrieve_catalog")
    builder.add_edge("retrieve_catalog", "interpret")
    builder.add_conditional_edges("interpret", route, ["generate_sql", END])
    builder.add_edge("generate_sql", "validate_sql")
    builder.add_edge("validate_sql", "execute")
    builder.add_edge("execute", "validate_result")
    builder.add_edge("validate_result", "build_chart_narrative")
    builder.add_edge("build_chart_narrative", END)
    return builder.compile(checkpointer=checkpointer)
