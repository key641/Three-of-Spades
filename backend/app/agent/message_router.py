import json
import re
from enum import StrEnum

from pydantic import BaseModel

from app.agent.schemas import SessionState


class MessageIntentType(StrEnum):
    NEW_PLAN = "new_plan"
    MODIFY_PLAN = "modify_plan"
    REPLAN = "replan"
    ROUTE_DETAIL_QUESTION = "route_detail_question"
    GENERAL_CHAT = "general_chat"


class TurnType(StrEnum):
    NEW_PLAN = "new_plan"
    ADD_CONSTRAINT = "add_constraint"
    MODIFY_CONSTRAINT = "modify_constraint"
    REMOVE_CONSTRAINT = "remove_constraint"
    ROUTE_DETAIL = "route_detail"
    GENERAL_CHAT = "general_chat"


class PlanningMode(StrEnum):
    NEW_PLAN = "new_plan"
    FULL_REPLAN = "full_replan"
    PARTIAL_REPLAN = "partial_replan"
    ROUTE_DETAIL = "route_detail"
    GENERAL_CHAT = "general_chat"


class MessageRoute(BaseModel):
    intent_type: MessageIntentType
    turn_type: TurnType | None = None
    planning_mode: PlanningMode | None = None
    candidate_planning_modes: list[PlanningMode] = []
    confidence: float = 0
    raw_confidence: float | None = None
    confidence_source: str = ""
    confidence_reasons: list[str] = []
    reason: str = ""
    evidence: list[str] = []
    references_previous_route: bool = False
    inherit_previous: bool = False
    preserve_scenario: bool = False
    detail_type: str | None = None

    def model_post_init(self, __context) -> None:
        if self.planning_mode is not None:
            return
        if self.intent_type == MessageIntentType.NEW_PLAN:
            self.planning_mode = PlanningMode.NEW_PLAN
        elif self.intent_type == MessageIntentType.REPLAN:
            self.planning_mode = PlanningMode.PARTIAL_REPLAN
        elif self.intent_type == MessageIntentType.MODIFY_PLAN:
            self.planning_mode = PlanningMode.FULL_REPLAN
        elif self.intent_type == MessageIntentType.ROUTE_DETAIL_QUESTION:
            self.planning_mode = PlanningMode.ROUTE_DETAIL
        elif self.intent_type == MessageIntentType.GENERAL_CHAT:
            self.planning_mode = PlanningMode.GENERAL_CHAT


class MessageRouter:
    """Classifies the current chat turn before the route planning pipeline runs."""

    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    async def classify(self, message: str, state: SessionState) -> MessageRoute:
        # 先跑规则，高信心时直接返回，跳过 LLM（节省 3~5 秒）
        rule_route = self._fallback_classify(message, state)
        calibrated_rule = self._calibrator().calibrate(rule_route, message, state, source="rule_fast")
        if calibrated_rule.confidence >= 0.75:
            return calibrated_rule

        try:
            route = await self._classify_with_llm(message, state)
            return self._calibrator().calibrate(route, message, state, source="llm")
        except Exception:
            route = self._fallback_classify(message, state)
            return self._calibrator().calibrate(route, message, state, source="rule_fallback")

    def _calibrator(self):
        from app.agent.intent_confidence import IntentConfidenceCalibrator

        return IntentConfidenceCalibrator()

    async def _classify_with_llm(self, message: str, state: SessionState) -> MessageRoute:
        response = await self.llm_client.complete(
            [
                {
                    "role": "system",
                    "content": (
                        "你是路线规划 Agent 的消息路由器，只输出 JSON。"
                        "intent_type 只能是 new_plan、modify_plan、replan、route_detail_question、general_chat。"
                        "turn_type 只能是 new_plan、add_constraint、modify_constraint、remove_constraint、route_detail、general_chat。"
                        "planning_mode 只能是 new_plan、full_replan、partial_replan、route_detail、general_chat。"
                        "必须输出 confidence、reason、evidence。evidence 是用户原话里的关键短语数组。"
                        "candidate_planning_modes 只在用户原话确实无法区分多个规划方式时输出；如果原话已经明确，不要输出候选。"
                        "route_detail_question 表示用户在问上一轮已生成路线的细节，例如两点之间怎么去、某站排队多久、费用多少。"
                        "modify_plan 表示用户要修改上一轮路线并重新规划。"
                        "full_replan 表示基于偏好或整体目标重新生成一组候选方案，例如重新生成路线、重新规划、换一条路线、更省钱、少排队、整体不满意。"
                        "partial_replan 表示保留原方案并局部替换或调整，例如只替换这个地点、换一家、不喜欢这家、第二站换掉、下雨、堵车、关门、排队90分钟。"
                        "add_constraint 表示用户在上一轮基础上追加需求，例如“还要吃饭”“也想拍照”“加一个餐厅”，必须 inherit_previous=true。"
                        "如果只是追加需求而不是切换主题，preserve_scenario=true；只有“改成美食路线”“只想吃吃喝喝”这类明确切换才 preserve_scenario=false。"
                        "示例1：用户说“重新生成路线”，输出 planning_mode=full_replan，candidate_planning_modes=[]，confidence>=0.8。"
                        "示例2：用户说“只替换这个地点”，输出 intent_type=replan，planning_mode=partial_replan，candidate_planning_modes=[]，confidence>=0.8。"
                        "示例3：用户说“换个便宜点的”，可能是全量重规划也可能是局部替换，输出 candidate_planning_modes=[\"full_replan\",\"partial_replan\"]，confidence<0.5。"
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
                planning_mode=PlanningMode.ROUTE_DETAIL,
                confidence=0.55,
                references_previous_route=True,
                inherit_previous=True,
                detail_type="transport_between_stops",
            )
        if state.last_intent and self._looks_like_add_constraint(text):
            return MessageRoute(
                intent_type=MessageIntentType.MODIFY_PLAN,
                turn_type=TurnType.ADD_CONSTRAINT,
                planning_mode=PlanningMode.FULL_REPLAN,
                confidence=0.5,
                references_previous_route=True,
                inherit_previous=True,
                preserve_scenario=True,
            )
        if state.last_intent and self._looks_like_partial_replan(text):
            return MessageRoute(
                intent_type=MessageIntentType.REPLAN,
                turn_type=TurnType.MODIFY_CONSTRAINT,
                planning_mode=PlanningMode.PARTIAL_REPLAN,
                confidence=0.55,
                references_previous_route=True,
                inherit_previous=True,
                preserve_scenario=True,
            )
        if state.last_intent and self._looks_like_ambiguous_replan(text):
            return MessageRoute(
                intent_type=MessageIntentType.MODIFY_PLAN,
                turn_type=TurnType.MODIFY_CONSTRAINT,
                planning_mode=PlanningMode.FULL_REPLAN,
                candidate_planning_modes=[PlanningMode.FULL_REPLAN, PlanningMode.PARTIAL_REPLAN],
                confidence=0.35,
                references_previous_route=True,
                inherit_previous=True,
                preserve_scenario=True,
            )
        if state.last_intent and self._looks_like_full_replan(text):
            return MessageRoute(
                intent_type=MessageIntentType.MODIFY_PLAN,
                turn_type=TurnType.MODIFY_CONSTRAINT,
                planning_mode=PlanningMode.FULL_REPLAN,
                confidence=0.75,
                references_previous_route=True,
                inherit_previous=True,
                preserve_scenario=True,
            )
        if self._looks_like_route_related(text):
            intent_type = MessageIntentType.MODIFY_PLAN if state.last_intent else MessageIntentType.NEW_PLAN
            return MessageRoute(
                intent_type=intent_type,
                turn_type=TurnType.MODIFY_CONSTRAINT if state.last_intent else TurnType.NEW_PLAN,
                planning_mode=PlanningMode.FULL_REPLAN if state.last_intent else PlanningMode.NEW_PLAN,
                confidence=0.45,
                references_previous_route=state.last_intent is not None,
                inherit_previous=state.last_intent is not None,
            )
        return MessageRoute(
            intent_type=MessageIntentType.GENERAL_CHAT,
            turn_type=TurnType.GENERAL_CHAT,
            planning_mode=PlanningMode.GENERAL_CHAT,
            confidence=0.4,
        )

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
            "推荐",
            "有推荐",
            "去哪",
            "哪里玩",
            "怎么玩",
            "适合",
            "户外",
            "漫步",
            "散步",
            "城市漫步",
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
            "上海",
            "杭州",
            "北京",
            "广州",
            "深圳",
            "南京",
            "成都",
            "重庆",
            "苏州",
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

    def _looks_like_partial_replan(self, text: str) -> bool:
        local_terms = [
            "换一家",
            "换个店",
            "换一个店",
            "换掉",
            "替换",
            "不喜欢这家",
            "不想去这家",
            "这家太贵",
            "这家不好",
            "这个地方不想去",
            "第二站",
            "第三站",
            "当前路线",
            "这条路线",
        ]
        live_terms = [
            "下雨",
            "雨天",
            "堵车",
            "交通堵",
            "关门",
            "闭店",
            "临时关闭",
            "等位",
            "太累",
            "累了",
            "走不动",
        ]
        queue_event = "排队" in text and (
            bool(re.search(r"\d+\s*(分钟|小时)", text))
            or any(term in text for term in ["这家", "餐厅", "店", "现场", "突然", "临时"])
        )
        return any(term in text for term in local_terms) or any(term in text for term in live_terms) or queue_event

    def _looks_like_ambiguous_replan(self, text: str) -> bool:
        ambiguous_replace_terms = ["换个", "换一个", "换成", "这个不太行", "这个不行", "不太行"]
        global_preference_terms = ["便宜", "省钱", "少排队", "不排队", "少走路", "好吃", "亲子", "拍照"]
        return any(term in text for term in ambiguous_replace_terms) and any(term in text for term in global_preference_terms)

    def _looks_like_full_replan(self, text: str) -> bool:
        full_terms = [
            "更省钱",
            "便宜一点",
            "预算低",
            "少排队",
            "不排队",
            "少走路",
            "亲子友好",
            "适合拍照",
            "整体不满意",
            "重新生成",
            "重新生成路线",
            "重新给",
            "重新规划",
            "换个路线",
            "换一条路线",
            "不要商业街",
            "吃好一点",
        ]
        return any(term in text for term in full_terms)

    def _load_json_object(self, content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))
