from app.agent.memory import SessionMemory
from app.schemas.chat import AgentTraceStep, ChatRequest, ChatResponse
from app.schemas.intent import Intent
from app.schemas.route import RoutePlanRequest
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_service import RouteService


class AgentOrchestrator:
    """A-owned module: coordinates intent, profile, POI search, and route planning."""

    def __init__(self) -> None:
        self.memory = SessionMemory()
        self.profile_service = ProfileService()
        self.poi_service = POIService()
        self.route_service = RouteService()

    async def handle_message(self, request: ChatRequest) -> ChatResponse:
        trace: list[AgentTraceStep] = []

        intent = self._mock_parse_intent(request.message)
        trace.append(AgentTraceStep(step="parse_intent", label="解析用户意图", status="done"))

        user_profile = self.profile_service.get_profile(request.user_id)
        trace.append(AgentTraceStep(step="get_user_profile", label="读取用户画像", status="done"))

        strategy_weights = self.profile_service.build_strategy_weights(intent, user_profile)
        trace.append(AgentTraceStep(step="build_strategy_weights", label="生成偏好权重", status="done"))

        pois = self.poi_service.search(intent)
        trace.append(AgentTraceStep(step="search_pois", label="召回候选 POI", status="done"))

        routes = self.route_service.generate_routes(
            RoutePlanRequest(intent=intent, user_profile=user_profile, strategy_weights=strategy_weights, candidate_pois=pois)
        ).routes
        trace.append(AgentTraceStep(step="generate_routes", label="生成多目标路线", status="done"))

        self.memory.save_current_routes(request.session_id, routes)

        return ChatResponse(
            session_id=request.session_id,
            message="我先按你们的需求生成了几条可执行路线，后续可以继续让我少排队、更省钱或换一家。",
            need_clarification=False,
            clarifying_question=None,
            intent=intent,
            user_profile=user_profile,
            routes=routes,
            agent_trace=trace,
        )

    def _mock_parse_intent(self, message: str) -> Intent:
        preferences = ["吃好", "少排队", "拍照", "少走路"]
        if "省钱" in message or "便宜" in message:
            preferences.append("更省钱")
        if "亲子" in message or "小孩" in message:
            preferences.append("亲子友好")

        return Intent(
            city="上海",
            people_count=3 if "三" in message or "3" in message else 2,
            start_time="14:00",
            duration_hours=6,
            budget_per_person=300,
            preferences=preferences,
            avoid_tags=["排队久", "太贵"],
            scenario="friends_citywalk",
            need_clarification=False,
        )

