from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.chat import ChatRequest, ChatResponse


class EvaluationExpectation(BaseModel):
    expected_city: str | None = None
    expected_people_count: int | None = None
    expected_start_location_name: str | None = None
    expected_start_source: str | None = None
    expected_preferences: list[str] = Field(default_factory=list)
    expected_avoid_tags: list[str] = Field(default_factory=list)
    expected_required_roles: list[str] = Field(default_factory=list)
    min_routes: int = Field(default=0, ge=0)
    max_routes: int | None = Field(default=None, ge=0)
    expect_trace: bool = True
    expect_clarification: bool | None = None
    required_trace_steps: list[str] = Field(default_factory=list)
    forbidden_trace_steps: list[str] = Field(default_factory=list)
    require_planning_outcome: bool = True
    golden_patch: list[dict] = Field(default_factory=list)
    golden_state: dict = Field(default_factory=dict)
    required_tool_calls: list[str] = Field(default_factory=list)
    required_recovery_actions: list[str] = Field(default_factory=list)


class EvaluationCase(BaseModel):
    name: str
    message: str
    category: str = "通用"
    turns: list[str] = Field(default_factory=list, max_length=5)
    expectation: EvaluationExpectation = Field(default_factory=EvaluationExpectation)
    city: str | None = None
    location_city: str | None = None
    start_location_name: str | None = None
    start_lat: float | None = None
    start_lng: float | None = None
    user_id: str = "user_demo"


class EvaluationRunRequest(BaseModel):
    cases: list[EvaluationCase] = Field(default_factory=list, max_length=20)
    repeat_count: int = Field(default=1, ge=1, le=3)
    case_timeout_seconds: float = Field(default=30.0, ge=1.0, le=180.0)
    model_version: str | None = None
    prompt_version: str | None = None
    dataset_version: str = "eval-v3"
    strategy_version: str | None = None
    code_version: str | None = None


class EvaluationDimensionScore(BaseModel):
    dimension: str
    label: str
    score: int = Field(ge=0, le=100)
    passed_checks: int = 0
    total_checks: int = 0


class EvaluationIssueSummary(BaseModel):
    code: str
    label: str
    step: str
    count: int
    case_names: list[str] = Field(default_factory=list)


class EvaluationCaseResult(BaseModel):
    name: str
    category: str = "通用"
    passed: bool
    score: int = Field(default=0, ge=0, le=100)
    duration_ms: int
    problem_step: str | None = None
    failure_codes: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    warning_steps: list[str] = Field(default_factory=list)
    dimension_scores: list[EvaluationDimensionScore] = Field(default_factory=list)
    input: ChatRequest
    output: ChatResponse | None = None
    turn_outputs: list[ChatResponse] = Field(default_factory=list)
    error: str | None = None
    attempts: int = 1
    passed_attempts: int = 0
    stable_pass: bool = False
    attempt_durations_ms: list[int] = Field(default_factory=list)
    observed_patch: list[dict] = Field(default_factory=list)
    observed_state: dict = Field(default_factory=dict)
    observed_tool_calls: list[str] = Field(default_factory=list)
    observed_recovery_actions: list[str] = Field(default_factory=list)


class EvaluationSummary(BaseModel):
    total: int
    passed: int
    failed: int
    pass_rate: float
    average_score: float = 0
    duration_ms: int
    dimension_scores: list[EvaluationDimensionScore] = Field(default_factory=list)
    issues: list[EvaluationIssueSummary] = Field(default_factory=list)
    stable_passed: int = 0
    stable_pass_rate: float = 0
    versions: dict[str, str] = Field(default_factory=dict)


class EvaluationRunResponse(BaseModel):
    summary: EvaluationSummary
    results: list[EvaluationCaseResult]
