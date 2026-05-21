import unittest

from app.agent.route_detail_handler import RouteDetailHandler
from app.agent.schemas import SessionState
from app.schemas.route import Route, RouteScoreBreakdown, RouteStop


def build_route() -> Route:
    return Route(
        route_id="route_balanced",
        title="综合最优路线",
        objective="balanced",
        summary="测试路线",
        total_duration_minutes=180,
        total_cost_per_person=120,
        total_queue_minutes=5,
        total_travel_minutes=18,
        total_distance_km=2.4,
        score=86,
        score_breakdown=RouteScoreBreakdown(quality=88, queue=90, budget=82, distance=85, preference=86),
        stops=[
            RouteStop(
                poi_id="p1",
                name="静安雕塑公园",
                category="park",
                start_time="09:00",
                end_time="10:00",
                estimated_cost=0,
                queue_minutes=0,
                tags=["安静"],
            ),
            RouteStop(
                poi_id="p2",
                name="外滩观景平台",
                category="scenic",
                start_time="10:18",
                end_time="11:00",
                estimated_cost=0,
                queue_minutes=5,
                tags=["拍照"],
                travel_minutes_from_previous=18,
                distance_km_from_previous=2.4,
                transport_mode_from_previous="metro/taxi",
            ),
        ],
        reasons=["测试"],
    )


class RouteDetailHandlerTest(unittest.TestCase):
    def test_answers_transport_between_saved_route_stops(self) -> None:
        state = SessionState(session_id="s1", current_routes=[build_route()])

        response = RouteDetailHandler().answer("那俩地之间怎么过去", "s1", state)

        self.assertIn("静安雕塑公园", response.message)
        self.assertIn("外滩观景平台", response.message)
        self.assertIn("18 分钟", response.message)
        self.assertIn("2.4 公里", response.message)
        self.assertIn("地铁或打车", response.message)
        self.assertEqual(response.routes, state.current_routes)
        self.assertEqual(response.agent_trace[-1].step, "answer_route_detail")

    def test_asks_for_route_when_no_saved_routes_exist(self) -> None:
        response = RouteDetailHandler().answer("两个地点之间怎么过去", "s1", SessionState(session_id="s1"))

        self.assertTrue(response.need_clarification)
        self.assertIn("先生成一条路线", response.message)


if __name__ == "__main__":
    unittest.main()
