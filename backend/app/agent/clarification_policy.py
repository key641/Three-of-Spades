from pydantic import BaseModel, Field

from app.agent.message_router import MessageIntentType, MessageRoute, PlanningMode
from app.agent.schemas import SessionState
from app.schemas.chat import ChatRequest
from app.schemas.intent import Intent


class ClarificationDecision(BaseModel):
    need_clarification: bool = False
    clarification_type: str | None = None
    missing_field: str | None = None
    priority: str | None = None
    question: str = ""
    can_continue_with_defaults: bool = True
    candidate_intents: list[str] = Field(default_factory=list)


class ClarificationPolicy:
    """Decides when to ask a lightweight clarification before planning."""

    ROUTING_CONFIDENCE_THRESHOLD = 0.5

    def evaluate(
        self,
        request: ChatRequest,
        intent: Intent,
        message_route: MessageRoute,
        session_state: SessionState,
    ) -> ClarificationDecision:
        intent_decision = self._intent_disambiguation_decision(message_route)
        if intent_decision.need_clarification:
            return intent_decision

        if not self._needs_route_generation(message_route):
            return ClarificationDecision()

        if self._is_missing_city(request, intent, message_route, session_state):
            return ClarificationDecision(
                need_clarification=True,
                clarification_type="missing_required_field",
                missing_field="city",
                priority="required",
                question="你想在哪个城市或区域玩？我确认地点后就能先给你出一版路线。",
                can_continue_with_defaults=False,
            )

        if self._is_too_generic_new_plan(request.message, intent, message_route):
            return ClarificationDecision(
                need_clarification=True,
                clarification_type="missing_required_field",
                missing_field="trip_goal",
                priority="required",
                question="你这次主要想玩景点、吃美食，还是轻松 citywalk？我确认目标后再规划会更准。",
                can_continue_with_defaults=False,
            )

        return ClarificationDecision()

    def _intent_disambiguation_decision(self, message_route: MessageRoute) -> ClarificationDecision:
        candidate_modes = self._distinct_route_modes(message_route)
        if message_route.confidence >= self.ROUTING_CONFIDENCE_THRESHOLD or len(candidate_modes) < 2:
            return ClarificationDecision()

        return ClarificationDecision(
            need_clarification=True,
            clarification_type="intent_disambiguation",
            missing_field=None,
            priority="routing",
            question=self._intent_disambiguation_question(candidate_modes),
            can_continue_with_defaults=False,
            candidate_intents=[mode.value for mode in candidate_modes],
        )

    def _distinct_route_modes(self, message_route: MessageRoute) -> list[PlanningMode]:
        route_modes = {
            PlanningMode.NEW_PLAN,
            PlanningMode.FULL_REPLAN,
            PlanningMode.PARTIAL_REPLAN,
            PlanningMode.ROUTE_DETAIL,
        }
        modes: list[PlanningMode] = []
        for mode in [*message_route.candidate_planning_modes, message_route.planning_mode]:
            if mode in route_modes and mode not in modes:
                modes.append(mode)
        return modes

    def _intent_disambiguation_question(self, modes: list[PlanningMode]) -> str:
        mode_set = set(modes)
        if {PlanningMode.FULL_REPLAN, PlanningMode.PARTIAL_REPLAN} <= mode_set:
            return "你是想重新生成一条更符合新要求的路线，还是只想把当前路线里的某个地点换掉？"
        if {PlanningMode.NEW_PLAN, PlanningMode.ROUTE_DETAIL} <= mode_set:
            return "你是想重新规划一条路线，还是想问当前路线的细节？"
        if {PlanningMode.NEW_PLAN, PlanningMode.FULL_REPLAN} <= mode_set:
            return "你是想从头生成新路线，还是在上一条路线基础上整体调整？"
        return "我还不确定你想让我怎么处理，是重新规划、局部调整，还是只问路线细节？"

    def _needs_route_generation(self, message_route: MessageRoute) -> bool:
        return message_route.intent_type in {
            MessageIntentType.NEW_PLAN,
            MessageIntentType.MODIFY_PLAN,
            MessageIntentType.REPLAN,
        }

    def _is_missing_city(
        self,
        request: ChatRequest,
        intent: Intent,
        message_route: MessageRoute,
        session_state: SessionState,
    ) -> bool:
        if intent.city_from_message or request.city or self._message_mentions_city(request.message):
            return False
        if message_route.inherit_previous and session_state.last_intent and session_state.last_intent.city:
            return False
        if session_state.last_intent and session_state.last_intent.city and message_route.planning_mode != PlanningMode.NEW_PLAN:
            return False
        return message_route.planning_mode == PlanningMode.NEW_PLAN

    def _message_mentions_city(self, message: str) -> bool:
        known_cities = [
            "上海",
            "北京",
            "杭州",
            "成都",
            "广州",
            "深圳",
            "南京",
            "苏州",
            "重庆",
            "武汉",
            "西安",
            "长沙",
            "厦门",
            "天津",
        ]
        return any(city in message for city in known_cities)

    def _is_too_generic_new_plan(self, message: str, intent: Intent, message_route: MessageRoute) -> bool:
        if message_route.planning_mode != PlanningMode.NEW_PLAN:
            return False
        text = message.strip()
        if intent.preferences or intent.scenario not in {"", "friends_citywalk"}:
            return False
        generic_terms = ["安排一下", "规划一下", "推荐一下", "出去玩", "周末路线", "玩一天"]
        return any(term in text for term in generic_terms)
