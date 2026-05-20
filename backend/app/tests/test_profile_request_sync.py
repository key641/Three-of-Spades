import unittest

from app.schemas.chat import ChatRequest
from app.schemas.intent import Intent
from app.services.profile_service import ProfileService


class ProfileRequestSyncTest(unittest.TestCase):
    def test_chat_request_accepts_onboarding_profile_fields(self) -> None:
        request = ChatRequest(
            message="上海半天 citywalk，少排队",
            city="上海",
            scenarios=["friends_citywalk", "foodie_tour"],
            preferences=["少排队", "吃好"],
            avoid_tags=["人多"],
            budget_level="low",
            preference_weights={"quality": 0.2, "queue": 0.35, "distance": 0.2, "budget": 0.2, "preference": 0.05},
        )

        self.assertEqual(request.city, "上海")
        self.assertEqual(request.scenarios, ["friends_citywalk", "foodie_tour"])
        self.assertEqual(request.preferences, ["少排队", "吃好"])
        self.assertEqual(request.avoid_tags, ["人多"])
        self.assertEqual(request.budget_level, "low")
        self.assertEqual(request.preference_weights["queue"], 0.35)

    def test_profile_service_builds_profile_from_chat_request(self) -> None:
        request = ChatRequest(
            user_id="user_frontend",
            message="帮我规划路线",
            preferences=["少排队", "吃好"],
            avoid_tags=["人多"],
            preference_weights={"quality": 0.2, "queue": 0.35, "distance": 0.2, "budget": 0.2, "preference": 0.05},
        )

        profile = ProfileService().get_profile(request.user_id, request)

        self.assertEqual(profile.user_id, "user_frontend")
        self.assertEqual(profile.tags, ["少排队", "吃好"])
        self.assertEqual(profile.preferences, ["少排队", "吃好"])
        self.assertEqual(profile.avoid_tags, ["人多"])
        self.assertEqual(profile.preference_weights["queue"], 0.35)

    def test_profile_service_merges_request_fields_into_intent(self) -> None:
        request = ChatRequest(
            message="半天 citywalk",
            city="杭州",
            scenarios=["friends_citywalk"],
            preferences=["少排队"],
            avoid_tags=["商业街"],
            budget_level="low",
        )
        parsed_intent = Intent(city="上海", budget_per_person=300, preferences=["拍照"], avoid_tags=[])

        merged = ProfileService().merge_request_into_intent(parsed_intent, request)

        self.assertEqual(merged.city, "杭州")
        self.assertEqual(merged.scenario, "friends_citywalk")
        self.assertEqual(merged.preferences, ["拍照", "少排队"])
        self.assertEqual(merged.avoid_tags, ["商业街"])
        self.assertEqual(merged.budget_per_person, 100)

    def test_message_city_wins_over_onboarding_city(self) -> None:
        request = ChatRequest(message="我想要在上海一日游", city="北京")
        parsed_intent = Intent(city="上海", city_from_message=True)

        merged = ProfileService().merge_request_into_intent(parsed_intent, request)

        self.assertEqual(merged.city, "上海")

    def test_strategy_weights_keep_frontend_boosts(self) -> None:
        request = ChatRequest(
            message="少排队路线",
            preferences=["少排队"],
            preference_weights={"quality": 0.2, "queue": 0.35, "distance": 0.2, "budget": 0.2, "preference": 0.05},
        )
        service = ProfileService()
        profile = service.get_profile(request.user_id, request)

        weights = service.build_strategy_weights(Intent(preferences=["少排队"]), profile)

        self.assertEqual(weights.queue, 0.35)

    def test_profile_service_loads_seed_profile_when_request_has_no_profile(self) -> None:
        profile = ProfileService().get_profile("user_001", ChatRequest(user_id="user_001", message="帮我规划路线"))

        self.assertEqual(profile.user_id, "user_001")
        self.assertIn("拍照", profile.preferences)
        self.assertIn("排队", profile.avoid_tags)
        self.assertTrue(profile.preference_weights)


if __name__ == "__main__":
    unittest.main()
