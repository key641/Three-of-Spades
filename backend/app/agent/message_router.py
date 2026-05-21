import json
import re
from enum import StrEnum

from pydantic import BaseModel

from app.agent.schemas import SessionState


class MessageIntentType(StrEnum):
    NEW_PLAN = "new_plan"
    MODIFY_PLAN = "modify_plan"
    ROUTE_DETAIL_QUESTION = "route_detail_question"
    GENERAL_CHAT = "general_chat"


class TurnType(StrEnum):
    NEW_PLAN = "new_plan"
    ADD_CONSTRAINT = "add_constraint"
    MODIFY_CONSTRAINT = "modify_constraint"
    REMOVE_CONSTRAINT = "remove_constraint"
    ROUTE_DETAIL = "route_detail"
    GENERAL_CHAT = "general_chat"


class MessageRoute(BaseModel):
    intent_type: MessageIntentType
    turn_type: TurnType | None = None
    confidence: float = 0
    references_previous_route: bool = False
    inherit_previous: bool = False
    preserve_scenario: bool = False
    detail_type: str | None = None


class MessageRouter:
    """Classifies the current chat turn before the route planning pipeline runs."""

    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    async def classify(self, message: str, state: SessionState) -> MessageRoute:
        try:
            return await self._classify_with_llm(message, state)
        except Exception:
            return self._fallback_classify(message, state)

    async def _classify_with_llm(self, message: str, state: SessionState) -> MessageRoute:
        response = await self.llm_client.complete(
            [
                {
                    "role": "system",
                    "content": (
                        "你是路线规划 Agent 的消息路由器，只输出 JSON。"
                        "intent_type 只能是 new_plan、modify_plan、route_detail_question、general_chat。"
                        "turn_type 只能是 new_plan、add_constraint、modify_constraint、remove_constraint、route_detail、general_chat。"
                        "route_detail_question 表示用户在问上一轮已生成路线的细节，例如两点之间怎么去、某站排队多久、费用多少。"
                        "modify_plan 表示用户要修改上一轮路线并重新规划。"
                        "add_constraint 表示用户在上一轮基础上追加需求，例如“还要吃饭”“也想拍照”“加一个餐厅”，必须 inherit_previous=true。"
                        "如果只是追加需求而不是切换主题，preserve_scenario=true；只有“改成美食路线”“只想吃吃喝喝”这类明确切换才 preserve_scenario=false。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "message": message,
                            "has_previous_intent": state.last_intent is not None,
                            "has_current_routes": bool(state.current_routes),
                            "previous_intent": state.last_intent.model_dump() if state.last_intent else None,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            json_mode=True,
        )
        content = response["choices"][0]["message"]["content"]
        data = self._load_json_object(content)
        return MessageRoute.model_validate(data)

    def _fallback_classify(self, message: str, state: SessionState) -> MessageRoute:
        text = message.strip().lower()
        if self._looks_like_route_detail_question(text):
            return MessageRoute(
                intent_type=MessageIntentType.ROUTE_DETAIL_QUESTION,
                turn_type=TurnType.ROUTE_DETAIL,
                confidence=0.55,
                references_previous_route=True,
                inherit_previous=True,
                detail_type="transport_between_stops",
            )
        if state.last_intent and self._looks_like_add_constraint(text):
            return MessageRoute(
                intent_type=MessageIntentType.MODIFY_PLAN,
                turn_type=TurnType.ADD_CONSTRAINT,
                confidence=0.5,
                references_previous_route=True,
                inherit_previous=True,
                preserve_scenario=True,
            )
        if self._looks_like_route_related(text):
            intent_type = MessageIntentType.MODIFY_PLAN if state.last_intent else MessageIntentType.NEW_PLAN
            return MessageRoute(
                intent_type=intent_type,
                turn_type=TurnType.MODIFY_CONSTRAINT if state.last_intent else TurnType.NEW_PLAN,
                confidence=0.45,
                references_previous_route=state.last_intent is not None,
                inherit_previous=state.last_intent is not None,
            )
        return MessageRoute(intent_type=MessageIntentType.GENERAL_CHAT, turn_type=TurnType.GENERAL_CHAT, confidence=0.4)

    def _looks_like_route_detail_question(self, text: str) -> bool:
        detail_terms = ["怎么过去", "怎么去", "如何过去", "如何去", "两地", "两个地点", "之间", "交通", "打车", "地铁"]
        previous_terms = ["刚刚", "上面", "上一条", "这个路线", "这条路线", "那俩", "两个地点", "两地"]
        return any(term in text for term in detail_terms) and any(term in text for term in previous_terms)

    def _looks_like_route_related(self, text: str) -> bool:
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
        return any(keyword in text for keyword in route_keywords) or bool(re.search(r"\d+\s*(人|个|点|小时|分钟|元|块)", text))

    def _looks_like_add_constraint(self, text: str) -> bool:
        add_terms = ["还要", "也要", "还想", "也想", "加一个", "加个", "加上", "顺便", "安排"]
        constraint_terms = ["吃饭", "餐厅", "美食", "小吃", "咖啡", "拍照", "打卡", "少排队", "省钱", "少走路"]
        return any(term in text for term in add_terms) and any(term in text for term in constraint_terms)

    def _load_json_object(self, content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))
