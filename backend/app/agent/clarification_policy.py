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
    """
    Decides when to ask a lightweight clarification before planning.

    规则：
    - 每次会话最多追问 1 次（clarification_count >= 1 时跳过所有追问）
    - 单次追问最多合并 3 个问题，用换行分隔
    """

    ROUTING_CONFIDENCE_THRESHOLD = 0.5
    MAX_CLARIFICATION_ROUNDS = 1   # 最多追问 1 次
    MAX_QUESTIONS_PER_ROUND = 3    # 单次最多合并 3 个问题

    def evaluate(
        self,
        request: ChatRequest,
        intent: Intent,
        message_route: MessageRoute,
        session_state: SessionState,
    ) -> ClarificationDecision:
        # ── 已追问过，不再追问 ───────────────────────────────────
        if session_state.clarification_count >= self.MAX_CLARIFICATION_ROUNDS:
            return ClarificationDecision()

        intent_decision = self._intent_disambiguation_decision(message_route)
        if intent_decision.need_clarification:
            return intent_decision

        if not self._needs_route_generation(message_route):
            return ClarificationDecision()

        # ── 收集所有缺失字段对应的问题（最多 MAX_QUESTIONS_PER_ROUND 个）──
        questions: list[str] = []
        missing_fields: list[str] = []

        location_missing, location_question = self._is_missing_location(
            request, intent, message_route, session_state
        )
        if location_missing:
            questions.append(location_question)
            missing_fields.append("location")

        if self._is_too_generic_new_plan(request.message, intent, message_route):
            questions.append("你这次主要想玩景点、吃美食，还是轻松 citywalk？")
            missing_fields.append("trip_goal")

        # 人数/时长/预算等软约束（仅作为补充问题）
        if len(questions) < self.MAX_QUESTIONS_PER_ROUND:
            soft_q = self._soft_constraint_questions(request, intent, message_route)
            for q in soft_q:
                if len(questions) >= self.MAX_QUESTIONS_PER_ROUND:
                    break
                questions.append(q)

        if not questions:
            return ClarificationDecision()

        # 合并成一条追问（多问题用换行分隔，前缀数字）
        if len(questions) == 1:
            combined = questions[0]
        else:
            numbered = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
            combined = f"出发前帮我确认几点：\n{numbered}"

        return ClarificationDecision(
            need_clarification=True,
            clarification_type="missing_required_field",
            missing_field=missing_fields[0] if missing_fields else None,
            priority="required",
            question=combined,
            can_continue_with_defaults=False,
        )

    # ── 软约束补充问题 ────────────────────────────────────────────

    def _soft_constraint_questions(
        self,
        request: ChatRequest,
        intent: Intent,
        message_route: MessageRoute,
    ) -> list[str]:
        """返回人数/时长/预算等软约束的补充问题列表（仅在新计划场景且信息完全缺失时提）。"""
        if message_route.planning_mode != PlanningMode.NEW_PLAN:
            return []
        qs: list[str] = []
        # 人数
        if not intent.people_count and not request.trip_people:
            qs.append("大概几个人一起？")
        # 时长（不追问，系统默认即可）
        # 预算（不追问，偏好中包含即可）
        return qs

    # ── 路由歧义追问 ─────────────────────────────────────────────

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

    # ── 地点信息充足性判断 ───────────────────────────────────────

    def _is_missing_location(
        self,
        request: ChatRequest,
        intent: Intent,
        message_route: MessageRoute,
        session_state: SessionState,
    ) -> tuple[bool, str]:
        """
        判断是否缺少足够的地点信息。
        返回 (need_clarification, question)。

        不追问的条件（满足任意一个）：
          1. 消息中包含具体地点（区名、街道、景点、商圈等，而不仅仅是城市名）
          2. 有具体出发地名称（request.start_location_name 含区/街道级别信息）
          3. trip_city 或 LLM 解析出的城市是区级以下具体地点（如「上海静安区」）
          4. 继承了上一轮且上一轮有具体地点信息（modify/replan 场景）

        注意：GPS 仅代表知道出发点，不代表知道游玩目的地。
        仅有城市名（如「北京」）+ GPS → 仍需追问"在哪个区域逛"。
        """
        if not self._needs_route_generation(message_route):
            return False, ""

        # 继承上轮：modify/replan 且上一轮有地点信息 → 无需追问
        if message_route.planning_mode != PlanningMode.NEW_PLAN:
            last = session_state.last_intent
            if last and (last.start_location_name or last.start_lat or last.city):
                return False, ""

        # 消息里包含具体地点（区/街道/景点/商圈等）→ 不追问
        if self._message_mentions_specific_location(request.message):
            return False, ""

        # 有具体出发地/目的地名称（含区/街道级别信息）→ 不追问
        if request.start_location_name and self._is_specific_location(request.start_location_name):
            return False, ""
        if intent.start_location_name and self._is_specific_location(intent.start_location_name):
            return False, ""

        # 判断是否有具体目的地（区级以下）
        has_specific_dest = (
            (request.city and self._is_specific_location(request.city))
            or (intent.city and intent.city_from_message and self._is_specific_location(intent.city))
        )
        if has_specific_dest:
            return False, ""

        # 只有城市名（如「北京」）或者完全没有城市
        has_city_only = (
            (request.city and request.city.strip())
            or self._message_mentions_city(request.message)
            or (intent.city_from_message and intent.city)
            or (session_state.last_intent and session_state.last_intent.city
                and message_route.planning_mode != PlanningMode.NEW_PLAN)
        )

        has_gps = bool(
            (request.start_lat and request.start_lng)
            or (request.current_lat and request.current_lng)
        )

        if has_gps and has_city_only:
            return True, "你想在哪个区域逛？"
        elif has_gps and not has_city_only:
            return True, "你想在附近逛，还是去某个特定区域？"
        elif not has_city_only:
            return True, "你想在哪个城市逛？"
        else:
            return True, "你想在哪个区域逛？"

    def _is_specific_location(self, location: str) -> bool:
        """判断地点名称是否具体（含区/街道/景点，而非仅城市名）。"""
        if not location or len(location.strip()) <= 2:
            return False
        city_only = {
            "上海", "北京", "杭州", "成都", "广州", "深圳",
            "南京", "苏州", "重庆", "武汉", "西安", "长沙",
            "厦门", "天津", "青岛", "大连", "沈阳", "哈尔滨",
            "郑州", "合肥", "济南",
        }
        if location.strip() in city_only:
            return False
        specific_suffixes = [
            "区", "县", "镇", "街", "路", "道", "巷", "弄", "里",
            "站", "场", "园", "广场", "中心", "公园", "景区", "商圈",
            "mall", "Mall", "MALL", "步行街", "老街",
        ]
        return any(suf in location for suf in specific_suffixes) or len(location) >= 5

    def _message_mentions_city(self, message: str) -> bool:
        known_cities = [
            "上海", "北京", "杭州", "成都", "广州", "深圳",
            "南京", "苏州", "重庆", "武汉", "西安", "长沙",
            "厦门", "天津", "青岛", "大连", "沈阳", "郑州",
        ]
        return any(city in message for city in known_cities)

    def _message_mentions_specific_location(self, message: str) -> bool:
        """
        消息里是否包含具体地点信息（区/街道/景点/商圈），而不只是城市名。
        """
        import re
        non_district_endings = {"地区", "景区", "特区", "城区", "风景区", "保护区", "开发区", "区别", "区域"}
        for m in re.finditer(r"[\u4e00-\u9fa5]{2,6}区|[\u4e00-\u9fa5]{2,6}县|[\u4e00-\u9fa5]{2,6}新区", message):
            matched_text = m.group(0)
            tail2 = matched_text[-2:] if len(matched_text) >= 2 else matched_text
            if tail2 in non_district_endings or matched_text in non_district_endings:
                continue
            return True

        road_matches = re.findall(r"[\u4e00-\u9fa5]{2,8}(路|街|巷|弄|大道|步行街|老街)", message)
        false_positive_suffixes = {"路线", "路上", "路途", "路过", "路口", "路段", "街道", "街区"}
        real_road = False
        for match_end in re.finditer(r"[\u4e00-\u9fa5]{2,8}(路|街|巷|弄|大道|步行街|老街)", message):
            span_text = match_end.group(0)
            end_pos = match_end.end()
            next_char = message[end_pos:end_pos+1]
            if span_text + next_char in false_positive_suffixes or span_text in {"路线", "路上", "道路"}:
                continue
            if span_text.endswith("路") and next_char == "线":
                continue
            if span_text.endswith("路") and next_char in {"上", "途", "过", "口", "段", "程"}:
                continue
            if span_text.endswith("街") and next_char in {"道", "区"}:
                continue
            real_road = True
            break
        if real_road:
            return True

        landmark_keywords = [
            "外滩", "陆家嘴", "田子坊", "新天地", "南京路", "淮海路",
            "三里屯", "王府井", "后海", "什刹海", "南锣鼓巷", "国贸",
            "西湖", "灵隐", "断桥", "宽窄巷子", "锦里", "天府广场",
            "珠江新城", "北京路", "中山路", "鼓浪屿",
            "夫子庙", "玄武湖", "中山陵",
        ]
        if any(kw in message for kw in landmark_keywords):
            return True

        if re.search(r"在.{2,8}(附近|一带|周边|旁边|那边)", message):
            return True

        return False

    def _is_too_generic_new_plan(self, message: str, intent: Intent, message_route: MessageRoute) -> bool:
        if message_route.planning_mode != PlanningMode.NEW_PLAN:
            return False
        text = message.strip()
        if intent.preferences or intent.scenario not in {"", "friends_citywalk"}:
            return False
        generic_terms = ["安排一下", "规划一下", "推荐一下", "出去玩", "周末路线", "玩一天"]
        return any(term in text for term in generic_terms)
