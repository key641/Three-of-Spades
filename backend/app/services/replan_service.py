from app.schemas.route import ReplanRequest, RoutePlanResponse


class ReplanService:
    """B-owned module: partial replanning after queue, traffic, or preference events."""

    def replan(self, request: ReplanRequest) -> RoutePlanResponse:
        # TODO(B): preserve completed stops and replace impacted future POIs.
        updated_routes = request.current_routes
        for route in updated_routes:
            route.summary = f"已根据事件「{request.event_label}」重新评估，后续版本会替换受影响 POI。"
            route.replan_reason = "当前骨架先保留原路线，后续接入局部替换逻辑。"
        return RoutePlanResponse(routes=updated_routes)

