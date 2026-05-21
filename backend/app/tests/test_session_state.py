import unittest

from app.agent.memory import SessionMemory
from app.agent.schemas import AgentState, ChatTurn, SessionState
from app.schemas.chat import AgentTraceStep
from app.schemas.intent import Intent
from app.schemas.user import UserProfile


class SessionStateTest(unittest.TestCase):
    def test_session_memory_stores_structured_state(self) -> None:
        memory = SessionMemory()
        state = SessionState(
            session_id="s1",
            recent_messages=[
                ChatTurn(role="user", content="我想在上海一日游"),
                ChatTurn(role="assistant", content="已生成路线"),
            ],
            last_intent=Intent(city="上海", duration_hours=8),
            user_profile=UserProfile(user_id="u1", preferences=["少排队"], tags=["少排队"]),
        )

        memory.save_state(state)

        loaded = memory.get_state("s1")
        self.assertEqual(loaded.session_id, "s1")
        self.assertEqual(loaded.last_intent.city, "上海")
        self.assertEqual(loaded.recent_messages[-1].content, "已生成路线")
        self.assertEqual(loaded.user_profile.preferences, ["少排队"])

    def test_current_routes_helpers_remain_compatible(self) -> None:
        memory = SessionMemory()

        memory.save_current_routes("s1", [])

        self.assertEqual(memory.get_current_routes("s1"), [])
        self.assertEqual(memory.get_state("s1").current_routes, [])

    def test_agent_state_collects_current_turn_fields(self) -> None:
        state = AgentState(
            session_id="s1",
            message="预算低一点",
            intent=Intent(city="上海"),
            agent_trace=[AgentTraceStep(step="parse_intent", label="解析意图", status="done")],
        )

        self.assertEqual(state.session_id, "s1")
        self.assertEqual(state.intent.city, "上海")
        self.assertEqual(state.agent_trace[0].step, "parse_intent")


if __name__ == "__main__":
    unittest.main()
