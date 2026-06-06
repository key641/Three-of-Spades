from app.agent.schemas import ChatTurn, SessionState, TripState
from app.schemas.intent import Intent
from app.schemas.route import Route
from app.schemas.user import UserProfile


class SessionMemory:
    """A-owned module: lightweight in-memory session state for the demo."""

    def __init__(self) -> None:
        self._state_by_session: dict[str, SessionState] = {}

    def get_state(self, session_id: str) -> SessionState:
        return self._state_by_session.get(session_id) or SessionState(session_id=session_id)

    def save_state(self, state: SessionState) -> None:
        self._state_by_session[state.session_id] = state

    def save_current_routes(self, session_id: str, routes: list[Route]) -> None:
        state = self.get_state(session_id)
        state.current_routes = routes
        self.save_state(state)

    def get_current_routes(self, session_id: str) -> list[Route]:
        return self.get_state(session_id).current_routes

    def save_turn_result(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        intent: Intent,
        user_profile: UserProfile,
        routes: list[Route],
        trip_state: TripState | None = None,
        clarification_count: int | None = None,
    ) -> None:
        state = self.get_state(session_id)
        state.recent_messages = [
            *state.recent_messages,
            ChatTurn(role="user", content=user_message),
            ChatTurn(role="assistant", content=assistant_message),
        ][-12:]
        state.last_intent = intent
        state.trip_state = trip_state or TripState.from_intent(intent)
        state.user_profile = user_profile
        state.current_routes = routes
        if clarification_count is not None:
            state.clarification_count = clarification_count
        self.save_state(state)
