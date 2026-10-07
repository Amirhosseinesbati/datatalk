from datetime import date
from typing import Any
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from .catalog import DIMENSION_BY_KEY, METRIC_BY_KEY


class QueryPlan(BaseModel):
    metrics: list[str] = Field(min_length=1, max_length=3)
    dimensions: list[str] = Field(default_factory=list, max_length=2)
    start_date: date
    end_date: date
    date_basis: Literal["order_date", "refund_date"] = "order_date"
    comparison: Literal["none", "previous_period"] = "none"
    channel: str | None = None
    category: str | None = None
    product: str | None = None
    customer: str | None = None
    campaign: str | None = None
    top_n: int = Field(default=20, ge=1, le=50)
    sort: Literal["value_desc", "value_asc", "dimension_asc", "absolute_change_desc"] = "value_desc"
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_semantics(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must follow start_date")
        if (self.end_date - self.start_date).days > 730:
            raise ValueError("date range exceeds two years")
        if len(set(self.metrics)) != len(self.metrics) or any(k not in METRIC_BY_KEY for k in self.metrics):
            raise ValueError("unknown or duplicate metric")
        if len(set(self.dimensions)) != len(self.dimensions) or any(k not in DIMENSION_BY_KEY for k in self.dimensions):
            raise ValueError("unknown or duplicate dimension")
        if self.date_basis == "refund_date" and any(k != "refunds" for k in self.metrics):
            raise ValueError("refund-date analysis supports refunds only")
        return self


class PlanningDecision(BaseModel):
    kind: Literal["plan", "clarify", "reject"]
    plan: QueryPlan | None = None
    message: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AnalysisRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1200)


class ReportRequest(BaseModel):
    analysis_id: str
    title: str = Field(min_length=1, max_length=240)


class ImportPublishRequest(BaseModel):
    token: str


class UserOut(BaseModel):
    id: str
    email: str
    role: Literal["admin", "operator", "viewer"]
    workspace_id: str


class SessionOut(BaseModel):
    user: UserOut
    mode: str


class FreshnessOut(BaseModel):
    snapshot_id: str | None = None
    reference_date: str
    created_at: str
    hash: str
    id: str | None = None


class CatalogMetricOut(BaseModel):
    key: str
    name: str
    definition: str
    unit: str


class CatalogDimensionOut(BaseModel):
    key: str
    name: str


class CatalogOut(BaseModel):
    metrics: list[CatalogMetricOut]
    dimensions: list[CatalogDimensionOut]
    date_conventions: dict[str, str]
    source_tables: list[str]
    freshness: FreshnessOut | None
    synthetic: bool
    dataset_kind: Literal["synthetic", "imported", "mixed", "unknown"] = "unknown"


class QueryResultOut(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    row_cap: int
    query_duration_ms: float | None = None


class AnalysisEventOut(BaseModel):
    stage: str
    at: str


class AnalysisOut(BaseModel):
    id: str
    conversation_id: str
    question: str
    status: str
    stage: str
    clarification: str | None
    plan: QueryPlan | None
    sql: str | None
    parameters: dict[str, Any]
    result: QueryResultOut | None
    chart: dict[str, Any] | None
    narrative: str | None
    evidence: dict[str, Any] | None
    error: str | None
    events: list[AnalysisEventOut]
    snapshot: FreshnessOut | None
    created_at: str


class ConversationSummaryOut(BaseModel):
    id: str
    title: str
    created_at: str


class ConversationOut(ConversationSummaryOut):
    analyses: list[AnalysisOut]


class ConversationListOut(BaseModel):
    items: list[ConversationSummaryOut]


class ReportVersionSummaryOut(BaseModel):
    version: int
    created_at: str
    analysis_id: str


class ReportVersionOut(AnalysisOut):
    version: int
    version_created_at: str
    analysis_id: str
    model_version: str
    prompt_version: str
    source_tables: list[str]


class ReportOut(BaseModel):
    id: str
    title: str
    created_at: str
    current_version: int | None
    versions: list[ReportVersionSummaryOut]
    latest_version: ReportVersionOut | None


class ReportListOut(BaseModel):
    items: list[ReportOut]


class ReportRefreshOut(BaseModel):
    report_id: str
    analysis_id: str
    status: Literal["queued"]
    current_version: int


class ImportErrorOut(BaseModel):
    row: int
    message: str


class ImportPreviewOut(BaseModel):
    token: str
    accepted_count: int
    rejected_count: int
    errors: list[ImportErrorOut]
    preview: list[dict[str, Any]]


class ImportPublishOut(BaseModel):
    id: str
    status: str
    accepted_count: int
    rejected_count: int
    snapshot_id: str | None = None


class ImportSummaryOut(BaseModel):
    id: str
    filename: str
    status: str
    accepted_count: int
    rejected_count: int
    created_at: str


class ImportListOut(BaseModel):
    items: list[ImportSummaryOut]
