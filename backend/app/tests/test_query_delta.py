import unittest

from app.agent.intent_context import apply_query_delta
from app.agent.schemas import IntentDelta, QueryUnderstanding, SessionState, TripState
from app.schemas.intent import Intent


class QueryDeltaTest(unittest.TestCase):
    def test_add_food_delta_updates_trip_state_without_overwriting_trip_shape(self) -> None:
        previous_intent = Intent(
            city="上海",
            people_count=2,
            duration_hours=8,
            start_time="09:00",
            preferences=["拍照"],
            scenario="friends_citywalk",
        )
        state = SessionState(
            session_id="s1",
            last_intent=previous_intent,
            trip_state=TripState.from_intent(previous_intent),
        )
        parsed_intent = Intent(
            city="北京",
            people_count=1,
            duration_hours=4,
            preferences=["吃好"],
            scenario="foodie_tour",
        )
        understanding = QueryUnderstanding(
            turn_type="add_constraint",
            inherit_previous=True,
            preserve_scenario=True,
        )
        delta = IntentDelta(
            added_preferences=["吃好"],
            added_must_include=["meal_stop"],
            removed_implicit_needs=["meal_stop"],
        )

        merged_intent, trip_state, summary = apply_query_delta(parsed_intent, state, understanding, delta)

        self.assertEqual(merged_intent.city, "上海")
        self.assertEqual(merged_intent.people_count, 2)
        self.assertEqual(merged_intent.duration_hours, 8)
        self.assertEqual(merged_intent.start_time, "09:00")
        self.assertEqual(merged_intent.scenario, "friends_citywalk")
        self.assertEqual(merged_intent.preferences, ["拍照", "吃好"])
        self.assertEqual(trip_state.city, "上海")
        self.assertEqual(trip_state.people_count, 2)
        self.assertEqual(trip_state.duration_hours, 8)
        self.assertEqual(trip_state.soft_preferences, ["拍照", "吃好"])
        self.assertIn("meal_stop", trip_state.must_include)
        self.assertNotIn("meal_stop", trip_state.implicit_needs)
        self.assertIn("rest_stop", trip_state.implicit_needs)
        self.assertIn("city", summary.kept)
        self.assertIn("people_count", summary.kept)
        self.assertIn("meal_stop", summary.added)
        self.assertNotIn("meal_stop", summary.removed)

    def test_modify_city_delta_changes_only_city_and_keeps_previous_constraints(self) -> None:
        previous_intent = Intent(
            city="上海",
            people_count=2,
            duration_hours=8,
            start_time="09:00",
            preferences=["拍照", "少排队"],
            avoid_tags=["排队久"],
            scenario="friends_citywalk",
        )
        state = SessionState(
            session_id="s1",
            last_intent=previous_intent,
            trip_state=TripState.from_intent(previous_intent),
        )
        understanding = QueryUnderstanding(
            turn_type="modify_constraint",
            inherit_previous=True,
            preserve_scenario=True,
        )
        delta = IntentDelta(modified_hard_constraints={"city": "杭州"})

        merged_intent, trip_state, summary = apply_query_delta(Intent(), state, understanding, delta)

        self.assertEqual(merged_intent.city, "杭州")
        self.assertTrue(merged_intent.city_from_message)
        self.assertEqual(merged_intent.people_count, 2)
        self.assertEqual(merged_intent.duration_hours, 8)
        self.assertEqual(merged_intent.start_time, "09:00")
        self.assertEqual(merged_intent.preferences, ["拍照", "少排队"])
        self.assertEqual(merged_intent.avoid_tags, ["排队久"])
        self.assertEqual(trip_state.city, "杭州")
        self.assertEqual(trip_state.people_count, 2)
        self.assertEqual(trip_state.duration_hours, 8)
        self.assertEqual(summary.changed["city"], {"from": "上海", "to": "杭州"})

    def test_explicit_people_and_negative_meal_override_inherited_state(self) -> None:
        previous_intent = Intent(
            city="上海",
            people_count=1,
            duration_hours=8,
            start_time="09:00",
            preferences=["网红打卡", "吃好"],
            scenario="friends_citywalk",
        )
        previous_state = TripState.from_intent(previous_intent)
        previous_state.must_include = ["meal_stop"]
        state = SessionState(
            session_id="s1",
            last_intent=previous_intent,
            trip_state=previous_state,
        )
        parsed_intent = Intent(
            city="上海",
            people_count=2,
            duration_hours=4,
            preferences=["吃饭", "朋友同行"],
            scenario="friends_citywalk",
        )
        understanding = QueryUnderstanding(
            turn_type="add_constraint",
            inherit_previous=True,
            preserve_scenario=True,
        )
        delta = IntentDelta(
            modified_hard_constraints={"people_count": 2},
            added_preferences=["朋友同行"],
            removed_preferences=["吃好", "吃饭"],
            removed_implicit_needs=["meal_stop"],
            removed_must_include=["meal_stop"],
        )

        merged_intent, trip_state, summary = apply_query_delta(parsed_intent, state, understanding, delta)

        self.assertEqual(merged_intent.people_count, 2)
        self.assertEqual(merged_intent.duration_hours, 8)
        self.assertIn("朋友同行", merged_intent.preferences)
        self.assertNotIn("吃好", merged_intent.preferences)
        self.assertNotIn("吃饭", merged_intent.preferences)
        self.assertNotIn("meal_stop", trip_state.must_include)
        self.assertNotIn("meal_stop", trip_state.implicit_needs)
        self.assertEqual(summary.changed["people_count"], {"from": 1, "to": 2})
        self.assertIn("meal_stop", summary.removed)
        self.assertNotIn("meal_stop", summary.added)


if __name__ == "__main__":
    unittest.main()
