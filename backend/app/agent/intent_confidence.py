from app.agent.message_router import MessageIntentType, MessageRoute, PlanningMode, TurnType
from app.agent.schemas import SessionState


class IntentConfidenceCalibrator:
    """Calibrates route intent confidence into an explainable engineering score."""

    AMBIGUOUS_CONFIDENCE_CAP = 0.42

    def calibrate(self, route: MessageRoute, message: str, state: SessionState, source: str) -> MessageRoute:
        reasons: list[str] = []
        raw_confidence = route.confidence if route.confidence > 0 else None

        if source == "rule_fallback" and raw_confidence is not None and not route.candidate_planning_modes:
            return route.model_copy(
                update={
                    "raw_confidence": raw_confidence,
                    "confidence": self._clamp(raw_confidence),
                    "confidence_source": "规则兜底",
                    "confidence_reasons": ["命中本地规则"],
                }
            )

        confidence = raw_confidence
        confidence_source = "LLM 返回" if source == "llm" and raw_confidence is not None else "后端校准"
        if confidence is None:
            confidence = self._base_confidence(route, message, state)
            reasons.append("模型未返回置信度，使用后端信号校准")

        confidence = self._clamp(confidence)

        explicit_mode = self._explicit_planning_mode(message)
        if explicit_mode is not None:
            route = self._apply_explicit_mode(route, explicit_mode)
            confidence = max(confidence, 0.75)
            confidence_source = "后端校准"
            reasons.append("用户原话已明确规划方式，清除歧义候选")

        if route.candidate_planning_modes:
            distinct_modes = self._distinct_modes(route)
            if len(distinct_modes) >= 2:
                confidence = min(confidence, self.AMBIGUOUS_CONFIDENCE_CAP)
                confidence_source = "后端校准"
                reasons.append("存在多个候选规划方式")

        if self._route_mode_conflicts(route):
            confidence = min(confidence, 0.45)
            confidence_source = "后端校准"
            reasons.append("意图类型和规划方式不完全一致")

        if source == "rule_fallback" and "命中本地规则" not in reasons:
            confidence_source = "规则兜底"
            reasons.append("命中本地规则")

        return route.model_copy(
            update={
                "raw_confidence": raw_confidence,
                "confidence": round(confidence, 2),
                "confidence_source": confidence_source,
                "confidence_reasons": reasons or ["未触发额外校准"],
            }
        )

    def _base_confidence(self, route: MessageRoute, message: str, state: SessionState) -> float:
        confidence = 0.5
        if route.intent_type == MessageIntentType.GENERAL_CHAT:
            confidence = 0.45
        if route.planning_mode == PlanningMode.NEW_PLAN and self._mentions_route_goal(message):
            confidence += 0.12
        if route.inherit_previous and state.last_intent:
            confidence += 0.08
        if route.references_previous_route and state.current_routes:
            confidence += 0.08
        return confidence

    def _distinct_modes(self, route: MessageRoute) -> list[PlanningMode]:
        modes: list[PlanningMode] = []
        for mode in [*route.candidate_planning_modes, route.planning_mode]:
            if mode and mode not in modes:
                modes.append(mode)
        return modes

    def _route_mode_conflicts(self, route: MessageRoute) -> bool:
        if route.intent_type == MessageIntentType.REPLAN and route.planning_mode != PlanningMode.PARTIAL_REPLAN:
            return True
        if route.intent_type == MessageIntentType.MODIFY_PLAN and route.planning_mode == PlanningMode.NEW_PLAN:
            return True
        if route.intent_type == MessageIntentType.NEW_PLAN and route.planning_mode not in {PlanningMode.NEW_PLAN, None}:
            return True
        return False

    def _mentions_route_goal(self, message: str) -> bool:
        terms = ["游", "玩", "路线", "行程", "规划", "citywalk", "餐厅", "景点"]
        return any(term in message for term in terms)

    def _explicit_planning_mode(self, message: str) -> PlanningMode | None:
        text = message.strip().lower()
        full_replan_terms = [
            "重新生成路线",
            "重新生成",
            "重新规划",
            "重新给",
            "换一条路线",
            "换个路线",
            "整体重来",
            "全部重来",
        ]
        partial_replan_terms = [
            "只替换这个地点",
            "只换这个地点",
            "只替换",
            "只换掉",
            "换掉这家",
            "换掉这个",
            "替换这个",
            "第二站换",
            "第三站换",
        ]
        if any(term in text for term in partial_replan_terms):
            return PlanningMode.PARTIAL_REPLAN
        if any(term in text for term in full_replan_terms):
            return PlanningMode.FULL_REPLAN
        return None

    def _apply_explicit_mode(self, route: MessageRoute, mode: PlanningMode) -> MessageRoute:
        if mode == PlanningMode.PARTIAL_REPLAN:
            return route.model_copy(
                update={
                    "intent_type": MessageIntentType.REPLAN,
                    "turn_type": TurnType.MODIFY_CONSTRAINT,
                    "planning_mode": PlanningMode.PARTIAL_REPLAN,
                    "candidate_planning_modes": [],
                    "inherit_previous": True,
                    "references_previous_route": True,
                    "preserve_scenario": True,
                }
            )
        if mode == PlanningMode.FULL_REPLAN:
            return route.model_copy(
                update={
                    "intent_type": MessageIntentType.MODIFY_PLAN,
                    "turn_type": TurnType.MODIFY_CONSTRAINT,
                    "planning_mode": PlanningMode.FULL_REPLAN,
                    "candidate_planning_modes": [],
                    "inherit_previous": True,
                    "preserve_scenario": True,
                }
            )
        return route

    def _clamp(self, value: float) -> float:
        return max(0, min(1, value))
