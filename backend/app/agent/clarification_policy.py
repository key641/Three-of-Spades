from __future__ import annotations

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
    根据意图类型，按字段优先级（P0阻断 / P1重要 / P2次要）收集缺口，
    一轮最多合并 3 个问题，只追问一轮。

    规则：
    - clarification_count >= 1 时跳过所有追问
    - 先识别意图 → 按意图查缺失字段 → P0 优先于 P1 → 取前 3 个
    """

    MAX_CLARIFICATION_ROUNDS = 1
    MAX_QUESTIONS_PER_ROUND = 3

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

        if not self._needs_route_generation(message_route):
            return ClarificationDecision()

        gaps = self._collect_gaps(request, intent, message_route, session_state)
        if not gaps:
            return ClarificationDecision()

        selected_gaps = gaps[:self.MAX_QUESTIONS_PER_ROUND]
        groups = [self._build_group_for_gap(gap) for gap in selected_gaps]

        question_lines = []
        suffix_map = {"P0": "（必填）", "P1": "（可选）"}
        for i, gap in enumerate(selected_gaps):
            tag = suffix_map.get(gap["priority"], "")
            question_lines.append(f"{i + 1}. {gap['title']} {tag}")
        question = "\n".join(question_lines)

        has_p0 = any(g["priority"] == "P0" for g in selected_gaps)
        return ClarificationDecision(
            need_clarification=True,
            clarification_type="missing_fields",
            missing_field=selected_gaps[0]["field"],
            priority=selected_gaps[0]["priority"],
            question=question,
            can_continue_with_defaults=not has_p0,
            clarification_groups=groups,
            inferred_context=self._inferred_context(request, intent, message_route, session_state),
        )

    def _collect_gaps(
        self,
        request: ChatRequest,
        intent: Intent,
        message_route: MessageRoute,
        session_state: SessionState,
    ) -> list[dict[str, str]]:
        mode = message_route.planning_mode
        if mode == PlanningMode.NEW_PLAN:
            return self._collect_new_plan_gaps(request, intent, message_route, session_state)
        if mode == PlanningMode.FULL_REPLAN:
            return self._collect_full_replan_gaps(session_state)
        if mode == PlanningMode.PARTIAL_REPLAN:
            return self._collect_partial_replan_gaps(request, session_state)
        return []

    def _collect_new_plan_gaps(
        self,
        request: ChatRequest,
        intent: Intent,
        message_route: MessageRoute,
        session_state: SessionState,
    ) -> list[dict[str, str]]:
        gaps: list[dict[str, str]] = []

        if self._is_missing_city(request, intent, message_route, session_state):
            gaps.append({"priority": "P0", "field": "city", "title": "想去哪个城市？"})

        if self._is_too_generic_new_plan(request.message, intent, message_route):
            gaps.append({"priority": "P0", "field": "trip_goal", "title": "这次主要想体验什么？"})

        if self._is_missing_time(request, intent):
            gaps.append({"priority": "P1", "field": "time", "title": "几点出发、玩多久？"})

        return gaps

    def _collect_full_replan_gaps(self, session_state: SessionState) -> list[dict[str, str]]:
        if not session_state.last_intent:
            return [{"priority": "P0", "field": "previous_state", "title": "之前没有规划记录，想怎么安排？"}]
        return []

    def _collect_partial_replan_gaps(
        self,
        request: ChatRequest,
        session_state: SessionState,
    ) -> list[dict[str, str]]:
        gaps: list[dict[str, str]] = []

        if not session_state.current_routes:
            gaps.append({"priority": "P0", "field": "active_route", "title": "当前没有活跃路线，想规划什么样的？"})
            return gaps

        if not self._can_identify_target_stop(request.message, session_state):
            gaps.append({"priority": "P0", "field": "target_stop", "title": "你想换掉哪一站？"})

        return gaps

    def _can_identify_target_stop(self, message: str, session_state: SessionState) -> bool:
        import re
        if re.search(r"第\s*[一二三四五六七八九十\d]+\s*(?:站|个|家)", message):
            return True
        type_refs = ["午餐", "晚餐", "早饭", "咖啡", "甜品", "餐厅", "景点"]
        if any(term in message for term in type_refs):
            return True
        if session_state.current_routes:
            route = session_state.current_routes[0]
            stops = getattr(route, "stops", []) or []
            return len(stops) <= 1
        return False

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
        if not self._needs_route_generation(message_route):
            return False

        if message_route.inherit_previous or message_route.planning_mode != PlanningMode.NEW_PLAN:
            last = session_state.last_intent
            if last and last.city:
                return False

        if self._message_mentions_city(request.message):
            return False

        if intent.city_from_message and intent.city:
            return False

        if message_route.inherit_previous and session_state.last_intent and session_state.last_intent.city:
            return False

        if request.city and request.city.strip():
            return False

        lat = request.current_lat if request.current_lat is not None else request.start_lat
        lng = request.current_lng if request.current_lng is not None else request.start_lng
        if lat is not None and lng is not None and self._coords_to_city(lat, lng):
            return False

        return True

    def _coords_to_city(self, lat: float, lng: float) -> str:
        """Resolve common mainland-city GPS coordinates without an external API."""
        city_bounds = [
            ("北京", 39.4, 41.1, 115.4, 117.5),
            ("上海", 30.7, 31.9, 120.9, 122.0),
            ("广州", 22.5, 23.9, 112.9, 114.0),
            ("深圳", 22.3, 22.8, 113.7, 114.6),
            ("成都", 30.0, 31.3, 103.2, 104.9),
            ("杭州", 29.2, 30.6, 119.1, 120.7),
            ("南京", 31.2, 32.6, 118.3, 119.3),
            ("武汉", 29.9, 31.4, 113.7, 115.1),
            ("西安", 33.4, 34.6, 107.6, 109.5),
            ("重庆", 28.1, 32.2, 105.3, 110.2),
            ("厦门", 24.1, 24.7, 117.9, 118.4),
            ("天津", 38.5, 40.3, 116.7, 118.1),
            ("苏州", 30.7, 31.8, 119.9, 121.2),
            ("长沙", 27.8, 28.7, 112.3, 113.6),
            ("青岛", 35.5, 37.0, 119.3, 121.0),
            ("郑州", 34.2, 34.9, 113.0, 114.2),
            ("合肥", 31.4, 32.5, 116.8, 117.6),
            ("沈阳", 41.2, 42.0, 122.9, 123.8),
            ("哈尔滨", 45.4, 46.1, 125.9, 127.0),
            ("济南", 36.4, 37.3, 116.5, 117.5),
            ("昆明", 24.5, 25.3, 102.4, 103.1),
            ("大连", 38.8, 39.4, 121.2, 122.2),
            ("宁波", 29.4, 30.3, 121.0, 122.3),
        ]
        for city, lat_min, lat_max, lng_min, lng_max in city_bounds:
            if lat_min <= lat <= lat_max and lng_min <= lng <= lng_max:
                return city
        return ""

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
        ]
        return any(term in text for term in generic_terms)

    def _has_explicit_trip_goal(self, intent: Intent, message: str) -> bool:
        if not (intent.preferences or intent.interest_tags or intent.optimization_goals):
            return False
        generic_terms = ["出去玩", "玩玩", "安排", "规划", "推荐一个"]
        if any(term in message for term in generic_terms) and len(message) <= 10:
            return False
        return True

    def _is_missing_time(self, request: ChatRequest, intent: Intent) -> bool:
        if request.start_time:
            return False
        if self._has_specific_time_signal(request.message):
            return False
        return intent.start_time == "14:00" and intent.duration_hours == 6

    def _build_group_for_gap(self, gap: dict[str, str]) -> ClarificationGroup:
        field = gap["field"]
        is_required = gap["priority"] == "P0"
        if field == "city":
            return self._city_group()
        if field == "trip_goal":
            return self._trip_goal_group()
        if field == "time":
            return self._time_group()
        return ClarificationGroup(
            id=field,
            title=gap["title"],
            required=is_required,
        )

    def _has_time_signal(self, message: str) -> bool:
        terms = [
            "今天", "明天", "上午", "中午", "下午", "晚上", "今晚",
            "全天", "半天", "一日", "周末", "几点",
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
            "景点", "美食", "吃", "citywalk", "漫步", "户外",
            "亲子", "约会", "拍照", "博物馆", "咖啡", "逛",
        ]
        return any(term in message for term in terms)

    def _message_mentions_city(self, message: str) -> bool:
        known_cities = [
            "上海", "北京", "杭州", "成都", "广州", "深圳",
            "南京", "苏州", "重庆", "武汉", "西安", "长沙",
            "厦门", "天津", "青岛", "大连", "沈阳", "哈尔滨",
            "郑州", "合肥", "济南",
        ]
        return any(city in message for city in known_cities)

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
            title="想去哪个城市？",
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
            title="这次主要想体验什么？",
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
            title="几点出发、玩多久？",
            required=False,
            options=[
                ClarificationOption(id="morning_0900", label="09:00 出发，玩 4 小时", value={"start_time": "09:00", "duration_hours": 4}),
                ClarificationOption(id="noon_1200", label="12:00 出发，玩 5 小时", value={"start_time": "12:00", "duration_hours": 5}),
                ClarificationOption(id="afternoon_1400", label="14:00 出发，玩 4 小时", value={"start_time": "14:00", "duration_hours": 4}),
                ClarificationOption(id="full_day_1000", label="10:00 出发，玩 8 小时", value={"start_time": "10:00", "duration_hours": 8}),
                ClarificationOption(id="skip", label="先出路线，我自己调", value={}),
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
