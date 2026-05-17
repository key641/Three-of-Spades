from app.schemas.route import Route


class SessionMemory:
    """A-owned module: lightweight in-memory session state for the demo."""

    def __init__(self) -> None:
        self._routes_by_session: dict[str, list[Route]] = {}

    def save_current_routes(self, session_id: str, routes: list[Route]) -> None:
        self._routes_by_session[session_id] = routes

    def get_current_routes(self, session_id: str) -> list[Route]:
        return self._routes_by_session.get(session_id, [])

