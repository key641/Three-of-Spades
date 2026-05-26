import json
import logging
import re

from app.agent.memory import SessionMemory
from app.agent.intent_enhancer import enhance_intent_from_message
from app.agent.prompts import SYSTEM_PROMPT
from app.llm.provider import get_llm_client
from app.schemas.chat import AgentTraceStep, ChatRequest, ChatResponse
from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.route import Route
from app.schemas.route import RoutePlanRequest
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_service import RouteService


logger = logging.getLogger("app.agent.orchestrator")


class AgentOrchestrator:
    """A-owned module: coordinates intent, profile, POI search, and route planning."""

    def __init__(self) -> None:
        self.memory = SessionMemory()
        self.llm_client = get_llm_client()
        self.profile_service = ProfileService()
        self.poi_service = POIService()
        self.route_service = RouteService()

    async def handle_message(self, request: ChatRequest) -> ChatResponse:
        trace: list[AgentTraceStep] = []
        logger.info(
            "chat start session_id=%s user_id=%s event_type=%s message=%s",
            request.session_id,
            request.user_id,
            request.event_type,
            self._preview(request.message),
        )

        if not self._looks_route_related(request.message):
            return await self._handle_direct_llm_chat(request, trace)

        intent = await self._parse_intent(request.message, trace)
        intent = enhance_intent_from_message(intent, request.message)
        intent = self.profile_service.merge_request_into_intent(intent, request)
        logger.info("chat intent session_id=%s intent=%s", request.session_id, intent.model_dump())

        user_profile = self.profile_service.get_profile(request.user_id, request)
        trace.append(AgentTraceStep(step="get_user_profile", label="读取用户画像", status="done"))
        logger.info("step done session_id=%s step=get_user_profile profile=%s", request.session_id, user_profile.model_dump())

        strategy_weights = self.profile_service.build_strategy_weights(intent, user_profile)
        trace.append(AgentTraceStep(step="build_strategy_weights", label="生成偏好权重", status="done"))
        logger.info(
            "step done session_id=%s step=build_strategy_weights weights=%s",
            request.session_id,
            strategy_weights.model_dump(),
        )

        pois = self.poi_service.search(intent, user_profile=user_profile)
        trace.append(AgentTraceStep(step="search_pois", label="召回候选 POI", status="done"))
        logger.info(
            "step done session_id=%s step=search_pois count=%s pois=%s",
            request.session_id,
            len(pois),
            [poi.name for poi in pois],
        )

        routes = self.route_service.generate_routes(
            RoutePlanRequest(intent=intent, user_profile=user_profile, strategy_weights=strategy_weights, candidate_pois=pois)
        ).routes
        trace.append(AgentTraceStep(step="generate_routes", label="生成多目标路线", status="done"))
        logger.info(
            "step done session_id=%s step=generate_routes count=%s routes=%s",
            request.session_id,
            len(routes),
            [route.route_id for route in routes],
        )

        message = await self._summarize_route_result(intent, pois, routes, trace)

        self.memory.save_current_routes(request.session_id, routes)
        logger.info("chat done session_id=%s trace=%s", request.session_id, [step.model_dump() for step in trace])

        return ChatResponse(
            session_id=request.session_id,
            message=message,
            need_clarification=False,
            clarifying_question=None,
            intent=intent,
            user_profile=user_profile,
            routes=routes,
            agent_trace=trace,
        )

    async def _summarize_route_result(self, intent: Intent, pois: list[POI], routes: list[Route], trace: list[AgentTraceStep]) -> str:
        fallback_message = "我先按你们的需求生成了几条可执行路线，后续可以继续让我少排队、更省钱或换一家。"
        logger.info("step start step=summarize_routes mode=llm pois=%s routes=%s", len(pois), len(routes))

        try:
            summary_input = {
                "intent": intent.model_dump(),
                "candidate_pois": [
                    {
                        "name": poi.name,
                        "city": poi.city,
                        "category": poi.category,
                        "avg_price": poi.avg_price,
                        "rating": poi.rating,
                        "queue_minutes": poi.queue_minutes,
                        "visit_duration_minutes": poi.visit_duration_minutes,
                        "tags": poi.tags,
                        "negative_tags": poi.negative_tags,
                    }
                    for poi in pois[:8]
                ],
                "routes": [
                    {
                        "title": route.title,
                        "objective": route.objective,
                        "summary": route.summary,
                        "total_duration_minutes": route.total_duration_minutes,
                        "total_cost_per_person": route.total_cost_per_person,
                        "total_queue_minutes": route.total_queue_minutes,
                        "score": route.score,
                        "stops": [
                            {
                                "name": stop.name,
                                "category": stop.category,
                                "start_time": stop.start_time,
                                "end_time": stop.end_time,
                                "estimated_cost": stop.estimated_cost,
                                "queue_minutes": stop.queue_minutes,
                                "tags": stop.tags,
                            }
                            for stop in route.stops
                        ],
                        "reasons": route.reasons,
                    }
                    for route in routes[:3]
                ],
            }
            logger.info("summarize_routes input=%s", summary_input)
            response = await self.llm_client.complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是路线规划 Agent 的结果总结器。"
                            "根据已召回的 POI 和已生成的路线，用中文给用户做一个简短总结。"
                            "只总结给定内容，不要编造不存在的地点或路线。"
                            "如果 routes 为空，说明候选点不足，并建议用户换城市或补充偏好。"
                            "回复控制在 2 到 4 句话。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(summary_input, ensure_ascii=False),
                    },
                ],
                json_mode=False,
            )
            content = response["choices"][0]["message"]["content"].strip()
            trace.append(AgentTraceStep(step="summarize_routes", label="LLM 总结召回和路线结果", status="done"))
            logger.info("step done step=summarize_routes mode=llm content=%s", self._preview(content))
            return content or fallback_message
        except Exception as exc:
            trace.append(
                AgentTraceStep(
                    step="summarize_routes",
                    label=f"LLM 总结失败，使用 fallback：{type(exc).__name__}",
                    status="fallback",
                )
            )
            logger.exception("step failed step=summarize_routes mode=llm fallback=true error=%s", type(exc).__name__)
            return fallback_message

    async def _handle_direct_llm_chat(self, request: ChatRequest, trace: list[AgentTraceStep]) -> ChatResponse:
        logger.info("chat direct_llm start session_id=%s reason=not_route_related", request.session_id)
        try:
            response = await self.llm_client.complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是一个用于测试接入链路的中文助手。"
                            "当前消息和路线规划无关时，直接自然回复用户。"
                            "回复要简短，不要生成路线 JSON。"
                        ),
                    },
                    {"role": "user", "content": request.message},
                ],
                json_mode=False,
            )
            content = response["choices"][0]["message"]["content"]
            trace.append(AgentTraceStep(step="direct_llm_chat", label="非路线问题，直接 LLM 对话", status="done"))
            logger.info("chat direct_llm done session_id=%s content=%s", request.session_id, self._preview(content))
            return ChatResponse(
                session_id=request.session_id,
                message=content,
                need_clarification=False,
                clarifying_question=None,
                intent=None,
                user_profile=None,
                routes=[],
                agent_trace=trace,
            )
        except Exception as exc:
            trace.append(
                AgentTraceStep(
                    step="direct_llm_chat",
                    label=f"直接 LLM 对话失败：{type(exc).__name__}",
                    status="error",
                )
            )
            logger.exception("chat direct_llm failed session_id=%s error=%s", request.session_id, type(exc).__name__)
            return ChatResponse(
                session_id=request.session_id,
                message="直接 LLM 对话暂时失败了，但后端链路还在。你可以看终端日志定位具体错误。",
                need_clarification=False,
                clarifying_question=None,
                intent=None,
                user_profile=None,
                routes=[],
                agent_trace=trace,
            )

    def _looks_route_related(self, message: str) -> bool:
        text = message.strip().lower()
        if not text:
            return False

        route_keywords = [
            "路线",
            "规划",
            "行程",
            "出行",
            "旅游",
            "旅行",
            "游玩",
            "citywalk",
            "逛",
            "玩",
            "景点",
            "餐厅",
            "咖啡",
            "拍照",
            "预算",
            "排队",
            "便宜",
            "省钱",
            "亲子",
            "朋友",
            "情侣",
            "人均",
            "小时",
            "分钟",
            "上午",
            "下午",
            "晚上",
            "点",
            "上海",
            "杭州",
            "北京",
            "广州",
            "深圳",
            "南京",
            "成都",
            "重庆",
            "苏州",
        ]
        if any(keyword in text for keyword in route_keywords):
            return True

        return bool(re.search(r"\d+\s*(人|个|点|小时|分钟|元|块)", text))

    async def _parse_intent(self, message: str, trace: list[AgentTraceStep]) -> Intent:
        try:
            logger.info("step start step=parse_intent mode=llm")
            intent = await self._llm_parse_intent(message)
            trace.append(AgentTraceStep(step="parse_intent", label="LLM 解析用户意图", status="done"))
            logger.info("step done step=parse_intent mode=llm")
            return intent
        except Exception as exc:
            logger.exception("step failed step=parse_intent mode=llm fallback=true error=%s", type(exc).__name__)
            trace.append(
                AgentTraceStep(
                    step="parse_intent",
                    label=f"LLM 解析失败，使用 fallback：{type(exc).__name__}",
                    status="fallback",
                )
            )
            intent = self._mock_parse_intent(message)
            logger.info("step done step=parse_intent mode=fallback intent=%s", intent.model_dump())
            return intent

    async def _llm_parse_intent(self, message: str) -> Intent:
        schema_fields = {
            "city": "string, default 上海 when omitted",
            "people_count": "integer",
            "start_time": "HH:MM string",
            "duration_hours": "integer",
            "budget_per_person": "integer, CNY",
            "start_location_name": "string or null, route start place name when mentioned",
            "start_lat": "number or null, route start latitude when known",
            "start_lng": "number or null, route start longitude when known",
            "preferences": "array of short Chinese strings",
            "avoid_tags": "array of short Chinese strings",
            "scenario": "short snake_case string",
            "need_clarification": "boolean",
        }
        response = await self.llm_client.complete(
            [
                {
                    "role": "system",
                    "content": (
                        f"{SYSTEM_PROMPT}\n"
                        "你只负责把用户消息解析成路线规划 Intent。"
                        "必须只返回一个 JSON object，不要 Markdown，不要解释。"
                        "无论信息是否完整，都必须包含所有字段。"
                        "用户只打招呼或需求不清时，用默认值补齐字段，并把 need_clarification 设为 true。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"字段说明：{json.dumps(schema_fields, ensure_ascii=False)}\n用户消息：{message}",
                },
            ]
        )
        content = response["choices"][0]["message"]["content"]
        logger.info("intent raw_llm_content=%s", self._preview(content))
        parsed = Intent().model_dump()
        loaded = self._load_json_object(content)
        logger.info("intent loaded_json=%s", loaded)
        parsed.update(loaded)
        parsed = self._normalize_intent_data(parsed)
        logger.info("intent normalized_json=%s", parsed)
        return Intent.model_validate(parsed)

    def _load_json_object(self, content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

    def _normalize_intent_data(self, data: dict) -> dict:
        defaults = Intent().model_dump()
        normalized = defaults | data

        for key in ("city", "start_time", "scenario"):
            if not normalized.get(key):
                normalized[key] = defaults[key]
            else:
                normalized[key] = str(normalized[key])

        if normalized.get("start_location_name") is not None:
            normalized["start_location_name"] = str(normalized["start_location_name"])

        for key in ("start_lat", "start_lng"):
            normalized[key] = self._coerce_optional_float(normalized.get(key))

        for key in ("people_count", "duration_hours", "budget_per_person"):
            normalized[key] = self._coerce_int(normalized.get(key), defaults[key])
            if normalized[key] <= 0:
                normalized[key] = defaults[key]

        for key in ("preferences", "avoid_tags"):
            normalized[key] = self._coerce_string_list(normalized.get(key))

        value = normalized.get("need_clarification", defaults["need_clarification"])
        if isinstance(value, str):
            normalized["need_clarification"] = value.strip().lower() in {"true", "1", "yes", "y", "是", "需要"}
        elif value is None:
            normalized["need_clarification"] = defaults["need_clarification"]
        else:
            normalized["need_clarification"] = bool(value)

        return normalized

    def _coerce_int(self, value: object, default: int) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            digits = re.search(r"\d+", value)
            if digits:
                return int(digits.group(0))
            chinese_numbers = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
            for char, number in chinese_numbers.items():
                if char in value:
                    return number
        return default

    def _coerce_optional_float(self, value: object) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"-?\d+(?:\.\d+)?", value)
            if match:
                return float(match.group(0))
        return None

    def _coerce_string_list(self, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if isinstance(value, str):
            return [item.strip() for item in re.split(r"[,，、/|]", value) if item.strip()]
        return [str(value)]

    def _preview(self, value: str, limit: int = 800) -> str:
        return value if len(value) <= limit else f"{value[:limit]}..."

    def _mock_parse_intent(self, message: str) -> Intent:
        preferences = []
        if any(term in message for term in ["吃好", "美食", "餐厅", "小吃"]):
            preferences.append("吃好")
        if any(term in message for term in ["少排队", "别排队", "不排队", "不想排队"]):
            preferences.append("少排队")
        if any(term in message for term in ["拍照", "出片", "打卡", "citywalk", "街区"]):
            preferences.append("拍照")
        if any(term in message for term in ["少走路", "轻松", "别太累", "不要太累"]):
            preferences.append("少走路")
        if "省钱" in message or "便宜" in message:
            preferences.append("更省钱")
        if "亲子" in message or "小孩" in message:
            preferences.append("亲子友好")

        avoid_tags = []
        if any(term in message for term in ["人多", "拥挤", "人流密集"]):
            avoid_tags.append("人流密集")
        if any(term in message for term in ["排队久", "排队太久"]):
            avoid_tags.append("排队久")
        if any(term in message for term in ["太贵", "贵"]):
            avoid_tags.append("太贵")

        return Intent(
            city="上海",
            people_count=3 if "三" in message or "3" in message else 2,
            start_time="14:00",
            duration_hours=6,
            budget_per_person=300,
            preferences=preferences,
            avoid_tags=avoid_tags,
            scenario="friends_citywalk",
            need_clarification=False,
        )
