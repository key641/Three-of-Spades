from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.agent.v2.models import TripStateV2, TurnUnderstanding


class DecisionType(str, Enum):
    ANSWER_FROM_STATE = "answer_from_state"
    CLARIFY = "clarify"
    PLAN = "plan"
    REPLAN = "replan"
    REJECT = "reject"


class AgentDecision(BaseModel):
    decision: DecisionType
    blocking_fields: list[str] = Field(default_factory=list)
    question: str | None = None
    reason: str = ""


class AgentPolicy:
    def decide(self, state: TripStateV2, understanding: TurnUnderstanding) -> AgentDecision:
        if understanding.ambiguities:
            return AgentDecision(
                decision=DecisionType.CLARIFY,
                blocking_fields=list(understanding.ambiguities),
                question="我还需要确认一下：" + "、".join(understanding.ambiguities),
                reason="blocking_ambiguity",
            )
        if understanding.turn_type == "chat":
            return AgentDecision(decision=DecisionType.ANSWER_FROM_STATE, reason="general_chat")
        if understanding.turn_type == "route_question":
            if not state.current_route_ids:
                return AgentDecision(
                    decision=DecisionType.CLARIFY,
                    blocking_fields=["active_route"],
                    question="当前还没有可查询的路线，要先帮你规划一条吗？",
                    reason="missing_active_route",
                )
            return AgentDecision(decision=DecisionType.ANSWER_FROM_STATE, reason="route_question")
        if state.city is None:
            return AgentDecision(
                decision=DecisionType.CLARIFY,
                blocking_fields=["city"],
                question="你想在哪个城市安排这次行程？",
                reason="missing_city",
            )
        if understanding.turn_type == "replan":
            if not state.current_route_ids:
                return AgentDecision(
                    decision=DecisionType.CLARIFY,
                    blocking_fields=["active_route"],
                    question="当前没有活跃路线，请先告诉我想安排什么行程。",
                    reason="missing_active_route",
                )
            return AgentDecision(decision=DecisionType.REPLAN, reason="explicit_replan")
        return AgentDecision(decision=DecisionType.PLAN, reason="state_ready")
