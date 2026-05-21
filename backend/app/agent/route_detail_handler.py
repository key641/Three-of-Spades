from app.agent.schemas import SessionState
from app.schemas.chat import AgentTraceStep, ChatResponse
from app.schemas.route import RouteStop


class RouteDetailHandler:
    """Answers questions about the route already stored in session memory."""

    def answer(self, message: str, session_id: str, state: SessionState) -> ChatResponse:
        if not state.current_routes:
            return ChatResponse(
                session_id=session_id,
                message="我还没有可引用的路线。你可以先生成一条路线，我再帮你说明两点之间怎么过去。",
                need_clarification=True,
                clarifying_question="你想先规划哪座城市、什么时间段的路线？",
                intent=state.last_intent,
                user_profile=state.user_profile,
                routes=[],
                agent_trace=[AgentTraceStep(step="answer_route_detail", label="缺少上一轮路线，无法回答路线细节", status="fallback")],
            )

        route = state.current_routes[0]
        legs = self._transport_legs(route.stops)
        if not legs:
            message_text = f"当前路线「{route.title}」还没有足够的连续地点来说明两点之间怎么过去。"
        else:
            message_text = f"按当前路线「{route.title}」，两点之间可以这样走：\n" + "\n".join(legs)

        return ChatResponse(
            session_id=session_id,
            message=message_text,
            need_clarification=False,
            clarifying_question=None,
            intent=state.last_intent,
            user_profile=state.user_profile,
            routes=state.current_routes,
            agent_trace=[AgentTraceStep(step="answer_route_detail", label="读取上一轮路线并回答路段交通", status="done")],
        )

    def _transport_legs(self, stops: list[RouteStop]) -> list[str]:
        legs: list[str] = []
        for index in range(1, len(stops)):
            previous = stops[index - 1]
            current = stops[index]
            mode = self._format_transport_mode(current.transport_mode_from_previous)
            minutes = current.travel_minutes_from_previous
            distance = current.distance_km_from_previous
            detail_parts = [f"建议{mode}"]
            if minutes is not None:
                detail_parts.append(f"约 {minutes} 分钟")
            if distance is not None:
                detail_parts.append(f"约 {distance:g} 公里")
            legs.append(f"- 从{previous.name}到{current.name}：{'，'.join(detail_parts)}。")
        return legs

    def _format_transport_mode(self, mode: str | None) -> str:
        mode_labels = {
            "walk": "步行",
            "metro": "地铁",
            "taxi": "打车",
            "bike": "骑行",
            "bus": "公交",
            "drive": "自驾",
        }
        if mode == "walk":
            return "步行"
        if mode == "metro/taxi":
            return "地铁或打车"
        if mode == "taxi/metro":
            return "打车或地铁"
        if mode and "/" in mode:
            labels = [mode_labels.get(part, part) for part in mode.split("/") if part]
            if labels:
                return "或".join(labels[:2])
        if mode:
            return mode_labels.get(mode, mode)
        return "按路线衔接交通"
