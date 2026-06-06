from pydantic import BaseModel, Field

from app.agent.message_router import MessageIntentType, MessageRoute, PlanningMode
from app.agent.schemas import SessionState
from app.schemas.chat import ChatRequest, ClarificationGroup, ClarificationOption
from app.schemas.intent import Intent


class ClarificationDecision(BaseModel):
    need_clarification: bool = False
    clarification_type: str | None = None
    missing_field: str | None = None
    priority: str | None = None
    question: str = ""
    can_continue_with_defaults: bool = True
    candidate_intents: list[str] = Field(default_factory=list)
    clarification_groups: list[ClarificationGroup] = Field(default_factory=list)
    inferred_context: dict[str, object] = Field(default_factory=dict)


class ClarificationPolicy:
    """
    Decides when to ask a lightweight clarification before planning.

    规则：
    - 每次会话最多追问 1 次（clarification_count >= 1 时跳过所有追问）
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
        if session_state.clarification_count >= self.MAX_CLARIFICATION_ROUNDS:
            return ClarificationDecision()

        intent_decision = self._intent_disambiguation_decision(message_route)
        if intent_decision.need_clarification:
            return intent_decision

        if not self._needs_route_generation(message_route):
            return ClarificationDecision()

        new_plan_decision = self._new_plan_clarification_decision(request, intent, message_route, session_state)
        if new_plan_decision.need_clarification:
            return new_plan_decision
        return ClarificationDecision()

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
            priority="routing",
            question=self._intent_disambiguation_question(candidate_modes),
            can_continue_with_defaults=False,
            candidate_intents=[mode.value for mode in candidate_modes],
        )

    def _new_plan_clarification_decision(
        self,
        request: ChatRequest,
        intent: Intent,
        message_route: MessageRoute,
        session_state: SessionState,
    ) -> ClarificationDecision:
        if message_route.planning_mode != PlanningMode.NEW_PLAN:
            return ClarificationDecision()

        required_groups: list[ClarificationGroup] = []
        optional_groups: list[ClarificationGroup] = []
        inferred_context = self._inferred_context(request, intent, message_route, session_state)

        if self._is_missing_city(request, intent, message_route, session_state):
            required_groups.append(self._city_group())

        if self._is_too_generic_new_plan(request.message, intent, message_route):
            required_groups.append(self._trip_goal_group())

        if self._is_missing_time(request, intent) and (
            required_groups or self._looks_like_recommendation_prompt(request.message)
        ):
            required_groups.append(self._time_group())

        if self._looks_like_recommendation_prompt(request.message):
            if not self._has_companion_signal(request):
                optional_groups.append(self._companions_group())
            if not self._has_pace_signal(request.message, intent):
                optional_groups.append(self._pace_group())
            if not self._has_crowd_signal(request.message, intent):
                optional_groups.append(self._crowd_group())

        groups = [*required_groups, *optional_groups[:3]]
        if not groups:
            return ClarificationDecision()

        first_required = required_groups[0] if required_groups else None
        return ClarificationDecision(
            need_clarification=True,
            clarification_type="missing_required_field" if first_required else "new_plan_preferences",
            missing_field=first_required.id if first_required else None,
            priority="required" if first_required else "optional",
            question=(
                f"我先确认{self._required_group_names(required_groups)}，再给你规划路线。"
                if first_required
                else "我已经理解大方向了，再补几个偏好会让路线更贴合你。"
            ),
            can_continue_with_defaults=not bool(first_required),
            clarification_groups=groups,
            inferred_context=inferred_context,
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
        return "我还不确定你想让我怎么处理：重新规划、局部调整，还是只问路线细节？"

    def _needs_route_generation(self, message_route: MessageRoute) -> bool:
        return message_route.intent_type in {
            MessageIntentType.NEW_PLAN,
            MessageIntentType.MODIFY_PLAN,
            MessageIntentType.REPLAN,
        }

    # ── 地点信息充足性判断 ───────────────────────────────────────

    def _is_missing_city(
        self,
        request: ChatRequest,
        intent: Intent,
        message_route: MessageRoute,
        session_state: SessionState,
    ) -> bool:
        """
        判断是否仍然缺少足够明确的城市/区域信息。

        只要消息里已经包含具体地点、已有明确出发地，或者改写/重规划时能继承上一轮地点，
        就不应再把城市信息视为缺失。
        """
        if not self._needs_route_generation(message_route):
            return False

        if message_route.inherit_previous or message_route.planning_mode != PlanningMode.NEW_PLAN:
            last = session_state.last_intent
            if last and (last.start_location_name or last.start_lat or last.city):
                return False

        if self._message_mentions_specific_location(request.message):
            return False

        if request.start_location_name and self._is_specific_location(request.start_location_name):
            return False
        if intent.start_location_name and self._is_specific_location(intent.start_location_name):
            return False

        if (request.city and self._is_specific_location(request.city)) or (
            intent.city and intent.city_from_message and self._is_specific_location(intent.city)
        ):
            return False

        has_city_only = (
            (request.city and request.city.strip())
            or self._message_mentions_city(request.message)
            or (intent.city_from_message and intent.city)
            or (
                session_state.last_intent
                and session_state.last_intent.city
                and (message_route.inherit_previous or message_route.planning_mode != PlanningMode.NEW_PLAN)
            )
        )

        return not has_city_only

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
        if message_route.inherit_previous or message_route.planning_mode != PlanningMode.NEW_PLAN:
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
                and (message_route.inherit_previous or message_route.planning_mode != PlanningMode.NEW_PLAN))
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
            "青岛",
            "大连",
            "沈阳",
            "郑州",
            "合肥",
            "济南",
            "涓婃捣",
            "鍖椾含",
            "鏉窞",
            "鎴愰兘",
            "骞垮窞",
            "娣卞湷",
            "鍗椾含",
            "鑻忓窞",
            "閲嶅簡",
            "姝︽眽",
            "瑗垮畨",
            "闀挎矙",
            "鍘﹂棬",
            "澶╂触",
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
        if self._has_trip_goal_signal(text):
            return False
        if self._has_explicit_trip_goal(intent, text):
            return False
        generic_terms = [
            "安排一个",
            "规划一个",
            "推荐一个",
            "出去玩",
            "周末路线",
            "玩一天",
            "帮我安排",
            "瀹夋帓涓€涓?",
            "瑙勫垝涓€涓?",
            "鎺ㄨ崘涓€涓?",
            "鍑哄幓鐜?",
            "鍛ㄦ湯璺嚎",
            "鐜╀竴澶?",
        ]
        return any(term in text for term in generic_terms)

    def _has_explicit_trip_goal(self, intent: Intent, message: str) -> bool:
        if not (intent.preferences or intent.interest_tags or intent.optimization_goals):
            return False
        generic_terms = ["出去玩", "玩玩", "安排", "规划", "推荐", "周末", "鍑哄幓鐜?", "瀹夋帓", "瑙勫垝", "鎺ㄨ崘", "鍛ㄦ湯"]
        return not any(term in message for term in generic_terms)

    def _is_missing_time(self, request: ChatRequest, intent: Intent) -> bool:
        if request.start_time:
            return False
        if self._has_specific_time_signal(request.message):
            return False
        return intent.start_time == "14:00" and intent.duration_hours == 6

    def _looks_like_recommendation_prompt(self, message: str) -> bool:
        terms = ["推荐吗", "有推荐", "去哪", "哪里玩", "出去玩", "玩玩", "周末", "安排", "规划", "路线", "怎么玩", "鎺ㄨ崘", "瀹夋帓", "瑙勫垝"]
        return any(term in message for term in terms)

    def _required_group_names(self, groups: list[ClarificationGroup]) -> str:
        names = {
            "city": "城市",
            "trip_goal": "出行目标",
            "time": "时间",
        }
        labels = [names.get(group.id, group.title) for group in groups]
        return "、".join(labels) if labels else "几个必要信息"

    def _has_time_signal(self, message: str) -> bool:
        terms = [
            "今天",
            "明天",
            "上午",
            "中午",
            "下午",
            "晚上",
            "今晚",
            "全天",
            "半天",
            "一日",
            "周末",
            "几点",
            "浠婂ぉ",
            "鏄庡ぉ",
            "涓婂崍",
            "涓嬪崍",
            "鏅氫笂",
            "鍏ㄥぉ",
            "鍗婂ぉ",
            "涓€鏃?",
            "鍛ㄦ湯",
        ]
        return any(term in message for term in terms) or bool(__import__("re").search(r"\d{1,2}\s*点", message))

    def _has_specific_time_signal(self, message: str) -> bool:
        import re

        chinese_numbers = "一二三四五六七八九十两"
        return bool(
            re.search(r"\d{1,2}\s*[:：]\s*\d{2}", message)
            or re.search(r"\d{1,2}\s*点", message)
            or re.search(rf"[{chinese_numbers}]{{1,3}}\s*点", message)
        )

    def _has_trip_goal_signal(self, message: str) -> bool:
        terms = [
            "景点",
            "美食",
            "吃",
            "citywalk",
            "漫步",
            "户外",
            "亲子",
            "约会",
            "拍照",
            "博物馆",
            "咖啡",
            "逛",
            "鏅偣",
            "缇庨",
            "鍚?",
            "婕",
            "鎴峰",
            "浜插瓙",
            "绾︿細",
            "鎷嶇収",
        ]
        return any(term in message for term in terms)

    def _has_companion_signal(self, request: ChatRequest) -> bool:
        if request.people_count is not None:
            return True
        message = request.message
        terms = [
            "一个人",
            "自己",
            "朋友",
            "情侣",
            "对象",
            "家人",
            "孩子",
            "亲子",
            "同学",
            "多人",
            "涓€涓汉",
            "鏈嬪弸",
            "瀹朵汉",
            "瀛╁瓙",
            "浜插瓙",
        ]
        return any(term in message for term in terms)

    def _has_pace_signal(self, message: str, intent: Intent) -> bool:
        terms = ["轻松", "悠闲", "慢", "别太累", "紧凑", "多逛", "随缘", "杞绘澗", "鎱?", "绱у噾"]
        return any(term in message for term in terms)

    def _has_crowd_signal(self, message: str, intent: Intent) -> bool:
        if intent.avoid_tags or "少排队" in intent.preferences or "少排队" in intent.optimization_goals:
            return True
        terms = ["人少", "安静", "避开人", "少排队", "不排队", "热闹", "人多", "瀹夐潤", "灏戞帓闃?", "浜哄"]
        return any(term in message for term in terms)

    def _inferred_context(
        self,
        request: ChatRequest,
        intent: Intent,
        message_route: MessageRoute,
        session_state: SessionState,
    ) -> dict[str, object]:
        context: dict[str, object] = {}
        if not self._is_missing_city(request, intent, message_route, session_state):
            context["city"] = request.city or intent.city or (session_state.last_intent.city if session_state.last_intent else "")
        if self._has_time_signal(request.message):
            context["time"] = self._compact_signal(request.message, ["今天", "明天", "上午", "下午", "晚上", "全天", "半天", "一日", "周末"])
        if intent.preferences or intent.interest_tags:
            context["trip_goal"] = [*intent.interest_tags, *intent.preferences]
        elif self._has_trip_goal_signal(request.message):
            context["trip_goal"] = self._compact_signal(request.message, ["户外", "漫步", "citywalk", "美食", "景点", "拍照", "亲子"])
        return {key: value for key, value in context.items() if value}

    def _compact_signal(self, message: str, candidates: list[str]) -> str:
        hits = [candidate for candidate in candidates if candidate in message]
        return "、".join(hits[:3])

    def _city_group(self) -> ClarificationGroup:
        return ClarificationGroup(
            id="city",
            title="你想在哪个城市或区域玩？",
            required=True,
            options=[
                ClarificationOption(id="shanghai", label="上海", value={"city": "上海"}),
                ClarificationOption(id="beijing", label="北京", value={"city": "北京"}),
                ClarificationOption(id="hangzhou", label="杭州", value={"city": "杭州"}),
                ClarificationOption(id="chengdu", label="成都", value={"city": "成都"}),
            ],
        )

    def _trip_goal_group(self) -> ClarificationGroup:
        return ClarificationGroup(
            id="trip_goal",
            title="这次主要想要哪种路线？",
            required=True,
            options=[
                ClarificationOption(id="sights", label="景点游玩", value={"interest_tags": ["景点", "经典"]}),
                ClarificationOption(id="food", label="美食路线", value={"interest_tags": ["美食"], "scenario": "foodie_tour"}),
                ClarificationOption(id="citywalk", label="轻松 citywalk", value={"interest_tags": ["citywalk"], "scenario": "friends_citywalk"}),
                ClarificationOption(id="family", label="亲子友好", value={"interest_tags": ["亲子"], "scenario": "family_trip"}),
            ],
        )

    def _time_group(self) -> ClarificationGroup:
        return ClarificationGroup(
            id="time",
            title="你想几点出发、预计玩多久？",
            required=True,
            options=[
                ClarificationOption(id="morning_0900", label="09:00 出发，玩 4 小时", value={"start_time": "09:00", "duration_hours": 4}),
                ClarificationOption(id="noon_1200", label="12:00 出发，玩 5 小时", value={"start_time": "12:00", "duration_hours": 5}),
                ClarificationOption(id="afternoon_1400", label="14:00 出发，玩 4 小时", value={"start_time": "14:00", "duration_hours": 4}),
                ClarificationOption(id="full_day_1000", label="10:00 出发，玩 8 小时", value={"start_time": "10:00", "duration_hours": 8}),
            ],
        )

    def _companions_group(self) -> ClarificationGroup:
        return ClarificationGroup(
            id="companions",
            title="和谁一起出行？",
            required=False,
            options=[
                ClarificationOption(id="solo", label="我一个人", value={"people_count": 1, "scenario": "solo_trip"}),
                ClarificationOption(id="couple", label="两人小约会", value={"people_count": 2, "scenario": "couple_date", "interest_tags": ["拍照", "氛围感"]}),
                ClarificationOption(id="family_group", label="家人 / 多人团", value={"scenario": "family_trip", "interest_tags": ["亲子"]}),
            ],
        )

    def _pace_group(self) -> ClarificationGroup:
        return ClarificationGroup(
            id="pace",
            title="今天的出行节奏想要怎样？",
            required=False,
            options=[
                ClarificationOption(id="relaxed", label="悠闲慢游，重在体验", value={"schedule_tightness": 0.25, "walking_tolerance": 0.35, "interest_tags": ["慢游"]}),
                ClarificationOption(id="compact", label="紧凑充实，多逛几处", value={"schedule_tightness": 0.8, "walking_tolerance": 0.7}),
                ClarificationOption(id="flexible", label="随缘就好", value={"schedule_tightness": 0.45}),
            ],
        )

    def _crowd_group(self) -> ClarificationGroup:
        return ClarificationGroup(
            id="crowd",
            title="热门点位人可能比较多，是否避开？",
            required=False,
            options=[
                ClarificationOption(id="avoid_crowd", label="避开人多，偏安静", value={"avoid_tags": ["人流密集", "排队久"], "crowd_tolerance": 0.25}),
                ClarificationOption(id="ok_hotspot", label="不介意，热闹也好", value={"crowd_tolerance": 0.75}),
                ClarificationOption(id="default", label="随便你安排", value={}),
            ],
        )
