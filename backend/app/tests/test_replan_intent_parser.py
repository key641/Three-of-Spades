import unittest

from app.agent.replan_intent_parser import ReplanIntentParser
from app.schemas.route import Route, RouteScoreBreakdown, RouteStop


def _route() -> Route:
    return Route(
        route_id="route_balanced",
        title="综合路线",
        objective="balanced",
        summary="测试路线",
        total_duration_minutes=180,
        total_cost_per_person=160,
        total_queue_minutes=15,
        total_travel_minutes=20,
        total_distance_km=2.5,
        score=86,
        score_breakdown=RouteScoreBreakdown(quality=86, queue=88, budget=80, distance=82, preference=84),
        stops=[
            RouteStop(
                poi_id="park_1",
                name="静安雕塑公园",
                category="park",
                start_time="09:00",
                end_time="10:00",
                estimated_cost=0,
                queue_minutes=0,
                tags=["安静"],
            ),
            RouteStop(
                poi_id="restaurant_1",
                name="上海老饭店",
                category="restaurant",
                start_time="10:20",
                end_time="11:30",
                estimated_cost=160,
                queue_minutes=15,
                tags=["本帮菜"],
            ),
        ],
        reasons=["测试"],
    )


class ReplanIntentParserTest(unittest.TestCase):
    def test_parse_replace_poi_for_disliked_shop(self) -> None:
        event = ReplanIntentParser().parse("不喜欢这家店，换一家", [_route()])

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "replace_poi")
        self.assertEqual(event.selected_route_id, "route_balanced")
        self.assertEqual(event.current_poi_id, "restaurant_1")
        self.assertEqual(event.event_payload["affected_poi_id"], "restaurant_1")
        self.assertTrue(event.event_payload["force_replace"])
        self.assertEqual(event.event_payload["replacement_category"], "restaurant")

    def test_parse_queue_spike_keeps_queue_minutes_out_of_trip_duration(self) -> None:
        event = ReplanIntentParser().parse("餐厅排队 90 分钟，帮我换一个等待时间短的替代方案", [_route()])

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "queue_spike")
        self.assertEqual(event.event_payload["queue_minutes"], 90)
        self.assertEqual(event.event_payload["affected_poi_id"], "restaurant_1")
        self.assertIn("排队久", event.event_payload["avoid_tags"])

    def test_parse_live_events_without_target_stop(self) -> None:
        parser = ReplanIntentParser()

        rain = parser.parse("下雨了怎么办", [_route()])
        traffic = parser.parse("路上临时堵车了", [_route()])

        self.assertEqual(rain.event_type, "weather_change")
        self.assertIn("室内", rain.event_payload["prefer_tags"])
        self.assertEqual(traffic.event_type, "traffic_jam")
        self.assertGreaterEqual(traffic.event_payload["traffic_multiplier"], 1.4)


if __name__ == "__main__":
    unittest.main()
