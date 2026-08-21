from __future__ import annotations

import asyncio
import time
from collections import Counter, defaultdict
from collections.abc import Callable

from app.agent.orchestrator import AgentOrchestrator
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.evaluation import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationDimensionScore,
    EvaluationExpectation,
    EvaluationIssueSummary,
    EvaluationRunRequest,
    EvaluationRunResponse,
    EvaluationSummary,
)


DEFAULT_EVALUATION_CASES = [
    EvaluationCase(
        name="明确城市与硬约束",
        category="意图理解",
        message="上海半天 citywalk，2 人，人均 300，少排队",
        expectation=EvaluationExpectation(
            expected_city="上海", expected_people_count=2, expected_preferences=["少排队"], min_routes=1,
        ),
        city="北京",
    ),
    EvaluationCase(
        name="指定起点优先于 GPS",
        category="起点定位",
        message="从国贸出发，推荐几个适合 6 人聚餐的餐厅",
        city="北京",
        start_lat=39.9962,
        start_lng=116.4753,
        expectation=EvaluationExpectation(
            expected_city="北京", expected_people_count=6, expected_start_location_name="国贸",
            expected_start_source="named", forbidden_trace_steps=["apply_gps_start"], min_routes=1,
        ),
    ),
    EvaluationCase(
        name="未指定起点使用 GPS",
        category="起点定位",
        message="推荐几个适合朋友聚餐的餐厅",
        city="北京",
        start_lat=39.9962,
        start_lng=116.4753,
        expectation=EvaluationExpectation(expected_start_source="gps", required_trace_steps=["apply_gps_start"], min_routes=1),
    ),
    EvaluationCase(
        name="缺少城市时追问",
        category="追问决策",
        message="周末想出去逛逛",
        expectation=EvaluationExpectation(expect_clarification=True, min_routes=0, require_planning_outcome=False),
    ),
    EvaluationCase(
        name="城市已知不重复追问城市",
        category="追问决策",
        message="来几个附近放松的地点，晚上出去转转",
        city="北京",
        start_lat=39.9962,
        start_lng=116.4753,
        expectation=EvaluationExpectation(expected_city="北京", expected_start_source="gps", min_routes=1),
    ),
    EvaluationCase(
        name="轻松偏好可执行路线",
        category="路线生成",
        message="北京一日游，想吃好但别太累",
        expectation=EvaluationExpectation(expected_city="北京", min_routes=1),
    ),
    EvaluationCase(
        name="少换乘与服务优先",
        category="偏好遵循",
        message="北京周末半日游，少换乘、服务优先",
        expectation=EvaluationExpectation(expected_city="北京", expected_preferences=["少换乘", "服务优先"], min_routes=1),
    ),
    EvaluationCase(
        name="多轮修改保留起点",
        category="多轮状态",
        message="从静安寺出发安排上海半日游",
        turns=["再少走路一点，预算降到人均 200"],
        expectation=EvaluationExpectation(
            expected_city="上海", expected_start_location_name="静安寺", expected_preferences=["少走路"], min_routes=1,
        ),
    ),
    EvaluationCase(
        name="杭州覆盖请求默认城市",
        category="意图理解",
        message="杭州周六逛一天，3 个人",
        city="北京",
        expectation=EvaluationExpectation(
            expected_city="杭州", expected_people_count=3, min_routes=0, require_planning_outcome=False,
        ),
    ),
    EvaluationCase(
        name="上海 GPS 附近推荐",
        category="起点定位",
        message="附近找几个适合散步和喝咖啡的地方",
        city="上海",
        start_lat=31.2304,
        start_lng=121.4737,
        expectation=EvaluationExpectation(
            expected_city="上海", expected_start_source="gps", required_trace_steps=["apply_gps_start"], min_routes=1,
        ),
    ),
    EvaluationCase(
        name="明确人数与预算",
        category="意图理解",
        message="北京 4 个人玩半天，人均预算 200 元",
        expectation=EvaluationExpectation(expected_city="北京", expected_people_count=4, min_routes=1),
    ),
    EvaluationCase(
        name="雨天室内方案",
        category="偏好遵循",
        message="上海明天下雨，安排一个室内半日游",
        expectation=EvaluationExpectation(expected_city="上海", expected_preferences=["室内"], min_routes=1),
    ),
    EvaluationCase(
        name="亲子轻松方案",
        category="偏好遵循",
        message="北京带娃玩一天，别太累",
        expectation=EvaluationExpectation(expected_city="北京", expected_preferences=["亲子", "少走路"], min_routes=1),
    ),
    EvaluationCase(
        name="夜景与晚间出行",
        category="偏好遵循",
        message="上海今晚想看看夜景，安排三四个小时",
        expectation=EvaluationExpectation(expected_city="上海", expected_preferences=["夜景"], min_routes=1),
    ),
    EvaluationCase(
        name="安静且避开人流",
        category="偏好遵循",
        message="北京找些安静的地方，不要人挤人",
        expectation=EvaluationExpectation(expected_city="北京", expected_preferences=["安静"], min_routes=1),
    ),
    EvaluationCase(
        name="口语化两人出行",
        category="鲁棒性",
        message="我俩在上海随便转转，别走太多路",
        expectation=EvaluationExpectation(
            expected_city="上海", expected_people_count=2, expected_preferences=["少走路"], min_routes=1,
        ),
    ),
    EvaluationCase(
        name="中英文混合 Citywalk",
        category="鲁棒性",
        message="北京 afternoon citywalk，想拍照和喝 coffee",
        expectation=EvaluationExpectation(expected_city="北京", expected_preferences=["拍照", "咖啡"], min_routes=1),
    ),
    EvaluationCase(
        name="多轮补充城市",
        category="多轮状态",
        message="周末想出去逛逛",
        turns=["就在北京，下午出发，轻松一点"],
        expectation=EvaluationExpectation(expected_city="北京", expected_preferences=["少走路"], min_routes=1),
    ),
    EvaluationCase(
        name="多轮更换明确起点",
        category="多轮状态",
        message="北京安排一个半日游",
        turns=["改成从国贸出发，少走路"],
        start_lat=39.9962,
        start_lng=116.4753,
        expectation=EvaluationExpectation(
            expected_city="北京", expected_start_location_name="国贸", expected_start_source="named",
            expected_preferences=["少走路"], forbidden_trace_steps=["apply_gps_start"], min_routes=1,
        ),
    ),
    EvaluationCase(
        name="预算降低但保留城市人数",
        category="多轮状态",
        message="上海 5 人聚餐，人均 400",
        turns=["太贵了，降到人均 200，其他不变"],
        expectation=EvaluationExpectation(expected_city="上海", expected_people_count=5, expected_preferences=["省钱"], min_routes=1),
    ),
]


DIMENSION_LABELS = {
    "understanding": "意图理解",
    "grounding": "起点定位",
    "dialog": "追问决策",
    "planning": "路线可执行性",
    "observability": "过程可观测性",
    "reliability": "系统稳定性",
}

ISSUE_META = {
    "wrong_city": ("城市识别错误", "parse_intent"),
    "wrong_people_count": ("人数理解错误", "parse_intent"),
    "missing_preference": ("偏好未被遵循", "parse_intent"),
    "missing_avoid_tag": ("避雷条件丢失", "parse_intent"),
    "wrong_start_name": ("指定起点未生效", "apply_named_start"),
    "wrong_start_source": ("起点来源优先级错误", "apply_gps_start"),
    "wrong_clarification": ("追问决策错误", "clarify_intent"),
    "too_few_routes": ("可执行路线不足", "generate_routes"),
    "too_many_routes": ("路线数量超出预期", "generate_routes"),
    "no_planning_outcome": ("既无路线也无有效追问", "generate_routes"),
    "invalid_route": ("路线结构或时间成本无效", "generate_routes"),
    "missing_trace": ("过程追踪缺失", "agent_trace"),
    "missing_trace_step": ("关键执行步骤缺失", "agent_trace"),
    "forbidden_trace_step": ("出现不应执行的步骤", "agent_trace"),
    "empty_output": ("最终回复为空", "summarize_routes"),
    "exception": ("系统执行异常", "exception"),
    "wrong_golden_patch": ("权威理解 Patch 不匹配", "understand_turn"),
    "wrong_golden_state": ("最终权威状态不匹配", "reduce_state"),
    "missing_tool_call": ("缺少预期工具调用", "tool_gateway"),
    "missing_recovery_action": ("缺少预期恢复动作", "diagnose_infeasibility"),
}


class EvaluationService:
    def __init__(self, orchestrator_factory: Callable[[], AgentOrchestrator] = AgentOrchestrator) -> None:
        self.orchestrator_factory = orchestrator_factory

    async def run(self, request: EvaluationRunRequest) -> EvaluationRunResponse:
        cases = request.cases or DEFAULT_EVALUATION_CASES
        started = time.perf_counter()
        results = [await self._run_case(case, index, request) for index, case in enumerate(cases)]
        duration_ms = round((time.perf_counter() - started) * 1000)
        passed = sum(result.passed for result in results)
        stable_passed = sum(result.stable_pass for result in results)
        versions = {
            key: value
            for key, value in {
                "model": request.model_version,
                "prompt": request.prompt_version,
                "dataset": request.dataset_version,
                "strategy": request.strategy_version,
                "code": request.code_version,
            }.items()
            if value
        }
        return EvaluationRunResponse(
            summary=EvaluationSummary(
                total=len(results),
                passed=passed,
                failed=len(results) - passed,
                pass_rate=round(passed / len(results), 4) if results else 0,
                average_score=round(sum(result.score for result in results) / len(results), 1) if results else 0,
                duration_ms=duration_ms,
                dimension_scores=self._aggregate_dimensions(results),
                issues=self._aggregate_issues(results),
                stable_passed=stable_passed,
                stable_pass_rate=round(stable_passed / len(results), 4) if results else 0,
                versions=versions,
            ),
            results=results,
        )

    async def _run_case(
        self,
        case: EvaluationCase,
        index: int,
        request: EvaluationRunRequest,
    ) -> EvaluationCaseResult:
        attempts: list[EvaluationCaseResult] = []
        for attempt in range(request.repeat_count):
            try:
                result = await asyncio.wait_for(
                    self._run_case_once(case, index, attempt),
                    timeout=request.case_timeout_seconds,
                )
            except TimeoutError:
                first_request = self._build_request(case, f"evaluation_timeout_{index}_{attempt}", case.message)
                result = EvaluationCaseResult(
                    name=case.name,
                    category=case.category,
                    passed=False,
                    score=0,
                    duration_ms=round(request.case_timeout_seconds * 1000),
                    problem_step="timeout",
                    failure_codes=["exception"],
                    failures=["单条评测超过时间预算"],
                    dimension_scores=[
                        EvaluationDimensionScore(
                            dimension="reliability", label=DIMENSION_LABELS["reliability"], score=0,
                            total_checks=1,
                        )
                    ],
                    input=first_request,
                    error="TimeoutError: evaluation case exceeded time budget",
                )
            attempts.append(result)

        primary = attempts[0]
        primary.attempts = len(attempts)
        primary.passed_attempts = sum(item.passed for item in attempts)
        primary.stable_pass = bool(attempts) and all(item.passed for item in attempts)
        primary.attempt_durations_ms = [item.duration_ms for item in attempts]
        return primary

    async def _run_case_once(self, case: EvaluationCase, index: int, attempt: int = 0) -> EvaluationCaseResult:
        session_id = f"evaluation_{time.time_ns()}_{index}_{attempt}"
        messages = [case.message, *case.turns]
        first_request = self._build_request(case, session_id, messages[0])
        started = time.perf_counter()
        outputs: list[ChatResponse] = []
        orchestrator = self.orchestrator_factory()
        try:
            for message in messages:
                outputs.append(await orchestrator.handle_message(self._build_request(case, session_id, message)))
        except Exception as exc:
            dimension_scores = [EvaluationDimensionScore(dimension="reliability", label="系统稳定性", score=0, total_checks=1)]
            return EvaluationCaseResult(
                name=case.name, category=case.category, passed=False, score=0,
                duration_ms=round((time.perf_counter() - started) * 1000), problem_step="exception",
                failure_codes=["exception"], failures=["系统执行异常"], dimension_scores=dimension_scores,
                input=first_request, turn_outputs=outputs, error=f"{type(exc).__name__}: {exc}",
            )

        response = outputs[-1]
        checks = self._evaluate(case.expectation, response)
        failed_checks = [check for check in checks if not check[2]]
        failure_codes = list(dict.fromkeys(check[1] for check in failed_checks))
        failures = [check[3] for check in failed_checks]
        dimension_scores = self._dimension_scores(checks)
        score = round(sum(item.score for item in dimension_scores) / len(dimension_scores)) if dimension_scores else 100
        warning_steps = [
            step.step for step in response.agent_trace
            if step.status.lower() in {"fallback", "warning", "error", "failed"}
        ]
        observed_patch, observed_state, observed_tools, observed_recovery = self._v3_observations(response)
        return EvaluationCaseResult(
            name=case.name, category=case.category, passed=not failures, score=score,
            duration_ms=round((time.perf_counter() - started) * 1000),
            problem_step=self._problem_step(failure_codes, response), failure_codes=failure_codes,
            failures=failures, warning_steps=warning_steps, dimension_scores=dimension_scores,
            input=first_request, output=response, turn_outputs=outputs,
            observed_patch=observed_patch,
            observed_state=observed_state,
            observed_tool_calls=observed_tools,
            observed_recovery_actions=observed_recovery,
        )

    @staticmethod
    def _build_request(case: EvaluationCase, session_id: str, message: str) -> ChatRequest:
        return ChatRequest(
            session_id=session_id, user_id=case.user_id, message=message, city=case.city,
            start_location_name=case.start_location_name, start_lat=case.start_lat, start_lng=case.start_lng,
            debug=True,
        )

    def _evaluate(self, exp: EvaluationExpectation, response: ChatResponse) -> list[tuple[str, str, bool, str]]:
        checks: list[tuple[str, str, bool, str]] = []
        intent = response.intent
        trace_steps = [step.step for step in response.agent_trace]

        def add(dimension: str, code: str, passed: bool, failure: str) -> None:
            checks.append((dimension, code, passed, failure))

        if exp.expected_city:
            actual = intent.city if intent else None
            add("understanding", "wrong_city", actual == exp.expected_city, f"城市识别：期望 {exp.expected_city}，实际 {actual or '空'}")
        if exp.expected_people_count is not None:
            actual = intent.people_count if intent else None
            add("understanding", "wrong_people_count", actual == exp.expected_people_count, f"人数识别：期望 {exp.expected_people_count}，实际 {actual}")
        actual_preferences = set((intent.preferences + intent.interest_tags + intent.optimization_goals) if intent else [])
        for value in exp.expected_preferences:
            add("understanding", "missing_preference", value in actual_preferences, f"偏好遵循：缺少“{value}”")
        for value in exp.expected_avoid_tags:
            add("understanding", "missing_avoid_tag", bool(intent and value in intent.avoid_tags), f"避雷条件：缺少“{value}”")

        if exp.expected_start_location_name:
            actual = intent.start_location_name if intent else None
            passed = bool(actual and exp.expected_start_location_name in actual)
            add("grounding", "wrong_start_name", passed, f"起点识别：期望包含 {exp.expected_start_location_name}，实际 {actual or '空'}")
        if exp.expected_start_source:
            source_steps = {"named": "apply_named_start", "gps": "apply_gps_start", "default": "apply_default_start"}
            expected_step = source_steps.get(exp.expected_start_source, exp.expected_start_source)
            add("grounding", "wrong_start_source", expected_step in trace_steps, f"起点来源：期望 {exp.expected_start_source}，实际步骤 {', '.join(trace_steps) or '空'}")

        if exp.expect_clarification is not None:
            add("dialog", "wrong_clarification", response.need_clarification == exp.expect_clarification, f"追问判断：期望 {exp.expect_clarification}，实际 {response.need_clarification}")

        add("planning", "too_few_routes", len(response.routes) >= exp.min_routes, f"路线生成：期望至少 {exp.min_routes} 条，实际 {len(response.routes)} 条")
        if exp.max_routes is not None:
            add("planning", "too_many_routes", len(response.routes) <= exp.max_routes, f"路线生成：期望至多 {exp.max_routes} 条，实际 {len(response.routes)} 条")
        if exp.require_planning_outcome:
            add("planning", "no_planning_outcome", bool(response.routes or response.need_clarification), "规划结果：既没有路线，也没有有效追问")
        for route in response.routes:
            valid = bool(route.stops and route.total_duration_minutes > 0 and route.total_cost_per_person >= 0)
            add("planning", "invalid_route", valid, f"路线结构：{route.route_id} 缺少站点或时间成本无效")

        if exp.expect_trace:
            add("observability", "missing_trace", bool(response.agent_trace), "过程追踪：agent_trace 为空")
        for step in exp.required_trace_steps:
            add("observability", "missing_trace_step", step in trace_steps, f"过程追踪：缺少步骤 {step}")
        for step in exp.forbidden_trace_steps:
            add("observability", "forbidden_trace_step", step not in trace_steps, f"过程追踪：不应执行步骤 {step}")
        add("reliability", "empty_output", bool(response.message.strip()), "最终输出：回复为空")
        observed_patch, observed_state, observed_tools, observed_recovery = self._v3_observations(response)
        if exp.golden_patch:
            expected = {
                (item.get("op"), item.get("path"), self._stable_value(item.get("value")))
                for item in exp.golden_patch
            }
            actual = {
                (item.get("op"), item.get("path"), self._stable_value(item.get("value")))
                for item in observed_patch
            }
            add("understanding", "wrong_golden_patch", expected <= actual, "Golden Patch 与本轮权威理解不一致")
        for key, value in exp.golden_state.items():
            add(
                "understanding", "wrong_golden_state", observed_state.get(key) == value,
                f"Golden State 字段不一致：{key}",
            )
        for tool in exp.required_tool_calls:
            add("observability", "missing_tool_call", tool in observed_tools, f"缺少工具调用：{tool}")
        for action in exp.required_recovery_actions:
            add("planning", "missing_recovery_action", action in observed_recovery, f"缺少恢复动作：{action}")
        return checks

    @staticmethod
    def _stable_value(value) -> str:
        import json
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    @staticmethod
    def _v3_observations(response: ChatResponse) -> tuple[list[dict], dict, list[str], list[str]]:
        patches: list[dict] = []
        tools: list[str] = []
        recovery: list[str] = []
        tool_names = {
            "resolve_location", "search_pois", "generate_routes", "diagnose_infeasibility",
            "relax_constraints", "replan_route", "answer_route_question",
        }
        for step in response.agent_trace:
            details = step.details or {}
            if step.step == "understand_turn":
                patches.extend(details.get("patches") or [])
            if step.step in tool_names:
                tools.append(step.step)
            recovery.extend(details.get("suggested_next_actions") or [])
            recovery_detail = details.get("recovery")
            if isinstance(recovery_detail, dict) and recovery_detail.get("action"):
                recovery.append(recovery_detail["action"])
        intent_state = (
            response.intent.model_dump(mode="json")
            if hasattr(response.intent, "model_dump")
            else dict(response.intent or {})
        )
        return patches, intent_state, list(dict.fromkeys(tools)), list(dict.fromkeys(recovery))

    @staticmethod
    def _dimension_scores(checks: list[tuple[str, str, bool, str]]) -> list[EvaluationDimensionScore]:
        grouped: dict[str, list[bool]] = defaultdict(list)
        for dimension, _, passed, _ in checks:
            grouped[dimension].append(passed)
        return [
            EvaluationDimensionScore(
                dimension=dimension, label=DIMENSION_LABELS[dimension],
                score=round(sum(values) / len(values) * 100), passed_checks=sum(values), total_checks=len(values),
            )
            for dimension, values in grouped.items()
        ]

    @staticmethod
    def _aggregate_dimensions(results: list[EvaluationCaseResult]) -> list[EvaluationDimensionScore]:
        totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for result in results:
            for item in result.dimension_scores:
                totals[item.dimension][0] += item.passed_checks
                totals[item.dimension][1] += item.total_checks
        return [
            EvaluationDimensionScore(
                dimension=dimension, label=DIMENSION_LABELS[dimension],
                score=round(passed / total * 100) if total else 0, passed_checks=passed, total_checks=total,
            )
            for dimension, (passed, total) in totals.items()
        ]

    @staticmethod
    def _aggregate_issues(results: list[EvaluationCaseResult]) -> list[EvaluationIssueSummary]:
        counts = Counter(code for result in results for code in result.failure_codes)
        cases: dict[str, list[str]] = defaultdict(list)
        for result in results:
            for code in result.failure_codes:
                cases[code].append(result.name)
        return [
            EvaluationIssueSummary(code=code, label=ISSUE_META[code][0], step=ISSUE_META[code][1], count=count, case_names=cases[code])
            for code, count in counts.most_common()
        ]

    @staticmethod
    def _problem_step(failure_codes: list[str], response: ChatResponse) -> str | None:
        for step in response.agent_trace:
            if step.status.lower() in {"error", "failed"}:
                return step.step
        return ISSUE_META[failure_codes[0]][1] if failure_codes else None
