import unittest
from pathlib import Path

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
            category_preferences={"museum": 0.8, "restaurant": 0.6},
            budget_sensitivity=0.7,
            walking_tolerance=0.4,
            crowd_tolerance=0.2,
            preferred_route_roles=["photo_stop"],
            preferred_experience_tags=["文艺"],
        )

        self.assertEqual(request.city, "上海")
        self.assertEqual(request.scenarios, ["friends_citywalk", "foodie_tour"])
        self.assertEqual(request.preferences, ["少排队", "吃好"])
        self.assertEqual(request.avoid_tags, ["人多"])
        self.assertEqual(request.budget_level, "low")
        self.assertEqual(request.preference_weights["queue"], 0.35)
        self.assertEqual(request.category_preferences["museum"], 0.8)
        self.assertEqual(request.budget_sensitivity, 0.7)
        self.assertEqual(request.walking_tolerance, 0.4)
        self.assertEqual(request.crowd_tolerance, 0.2)
        self.assertEqual(request.preferred_route_roles, ["photo_stop"])
        self.assertEqual(request.preferred_experience_tags, ["文艺"])

    def test_profile_service_builds_profile_from_chat_request(self) -> None:
        request = ChatRequest(
            user_id="user_frontend",
            message="帮我规划路线",
            preferences=["别排队", "好吃", "高性价比"],
            avoid_tags=["人多", "贵"],
            preference_weights={"quality": 0.2, "queue": 0.35, "distance": 0.2, "budget": 0.2, "preference": 0.05},
            category_preferences={"museum": 0.9},
            preferred_route_roles=["photo_stop"],
            preferred_experience_tags=["小众"],
            preferred_transport_modes=["metro"],
            budget_sensitivity=0.8,
            walking_tolerance=0.3,
            crowd_tolerance=0.2,
        )

        profile = ProfileService().get_profile(request.user_id, request)

        self.assertEqual(profile.user_id, "user_frontend")
        self.assertEqual(profile.tags, ["少排队", "吃好", "更省钱"])
        self.assertEqual(profile.preferences, ["少排队", "吃好", "更省钱"])
        self.assertEqual(profile.avoid_tags, ["人流密集", "太贵"])
        self.assertEqual(profile.preference_weights["queue"], 0.35)
        self.assertEqual(profile.category_preferences["museum"], 0.9)
        self.assertEqual(profile.preferred_route_roles, ["photo_stop"])
        self.assertEqual(profile.preferred_experience_tags, ["小众"])
        self.assertEqual(profile.preferred_transport_modes, ["metro"])
        self.assertEqual(profile.budget_sensitivity, 0.8)
        self.assertEqual(profile.walking_tolerance, 0.3)
        self.assertEqual(profile.crowd_tolerance, 0.2)

    def test_profile_service_merges_request_fields_into_intent(self) -> None:
        request = ChatRequest(
            message="半天 citywalk",
            city="杭州",
            scenarios=["friends_citywalk"],
            preferences=["别排队", "打卡"],
            avoid_tags=["人多", "贵"],
            budget_level="low",
        )
        parsed_intent = Intent(city="上海", budget_per_person=300, preferences=["拍照"], avoid_tags=[])

        merged = ProfileService().merge_request_into_intent(parsed_intent, request)

        self.assertEqual(merged.city, "杭州")
        self.assertEqual(merged.scenario, "friends_citywalk")
        self.assertEqual(merged.preferences, ["拍照", "少排队"])
        self.assertEqual(merged.avoid_tags, ["人流密集", "太贵"])
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

    def test_profile_service_updates_profile_from_chat_intent(self) -> None:
        runtime_path = Path(__file__).resolve().parents[2] / ".pytest_cache" / "runtime_profiles_update_test.json"
        runtime_path.unlink(missing_ok=True)
        service = ProfileService(runtime_data_path=runtime_path)
        profile = service.get_profile(
            "user_frontend",
            ChatRequest(user_id="user_frontend", message="初始化", preferences=["网红打卡"], avoid_tags=["商业街"]),
        )

        updated = service.update_from_chat(
            profile,
            Intent(preferences=["少排队", "更省钱"], avoid_tags=["排队久", "太贵"]),
        )

        self.assertEqual(updated.preferences, ["网红打卡", "少排队", "更省钱"])
        self.assertEqual(updated.tags, ["网红打卡", "少排队", "更省钱"])
        self.assertEqual(updated.avoid_tags, ["商业街", "排队久", "太贵"])
        self.assertGreaterEqual(updated.preference_weights["queue"], 0.3)
        self.assertGreaterEqual(updated.preference_weights["budget"], 0.3)

    def test_profile_service_persists_chat_profile_to_json(self) -> None:
        runtime_path = Path(__file__).resolve().parents[2] / ".pytest_cache" / "runtime_profiles_test.json"
        runtime_path.unlink(missing_ok=True)
        service = ProfileService(runtime_data_path=runtime_path)
        profile = service.get_profile(
            "user_persisted",
            ChatRequest(user_id="user_persisted", message="初始化", preferences=["吃好"], avoid_tags=[]),
        )

        service.update_from_chat(profile, Intent(preferences=["少排队"], avoid_tags=["排队久"]))
        loaded = ProfileService(runtime_data_path=runtime_path).get_profile("user_persisted")

        self.assertEqual(loaded.preferences, ["吃好", "少排队"])
        self.assertEqual(loaded.tags, ["吃好", "少排队"])
        self.assertEqual(loaded.avoid_tags, ["排队久"])
        self.assertGreaterEqual(loaded.preference_weights["queue"], 0.3)

    def test_profile_service_does_not_persist_trip_only_preferences(self) -> None:
        runtime_path = Path(__file__).resolve().parents[2] / ".pytest_cache" / "runtime_profiles_trip_only_test.json"
        runtime_path.unlink(missing_ok=True)
        service = ProfileService(runtime_data_path=runtime_path)
        profile = service.get_profile(
            "user_trip_only",
            ChatRequest(user_id="user_trip_only", message="初始化", preferences=["吃好"], avoid_tags=[]),
        )

        updated = service.update_from_chat(
            profile,
            Intent(preferences=["少排队"], avoid_tags=["排队久"]),
            message="这次北京半日游少排队一点",
        )
        loaded = ProfileService(runtime_data_path=runtime_path).get_profile("user_trip_only")

        self.assertIn("少排队", updated.preferences)
        self.assertEqual(loaded.preferences, ["吃好"])
        self.assertEqual(loaded.avoid_tags, [])

    def test_profile_service_persists_explicit_long_term_preferences(self) -> None:
        runtime_path = Path(__file__).resolve().parents[2] / ".pytest_cache" / "runtime_profiles_long_term_test.json"
        runtime_path.unlink(missing_ok=True)
        service = ProfileService(runtime_data_path=runtime_path)
        profile = service.get_profile(
            "user_long_term",
            ChatRequest(user_id="user_long_term", message="初始化", preferences=["吃好"], avoid_tags=[]),
        )

        service.update_from_chat(
            profile,
            Intent(preferences=["少排队"], avoid_tags=["排队久"]),
            message="以后我都不喜欢排队，尽量少排队",
        )
        loaded = ProfileService(runtime_data_path=runtime_path).get_profile("user_long_term")

        self.assertEqual(loaded.preferences, ["吃好", "少排队"])
        self.assertEqual(loaded.avoid_tags, ["排队久"])

    def test_profile_service_loads_seed_profile_when_request_has_no_profile(self) -> None:
        profile = ProfileService().get_profile("user_001", ChatRequest(user_id="user_001", message="帮我规划路线"))

        self.assertEqual(profile.user_id, "user_001")
        self.assertIn("拍照", profile.preferences)
        self.assertIn("排队", profile.avoid_tags)
        self.assertTrue(profile.preference_weights)
        self.assertEqual(profile.budget_sensitivity, 0.52)
        self.assertEqual(profile.walking_tolerance, 0.38)
        self.assertEqual(profile.crowd_tolerance, 0.27)
        self.assertEqual(profile.schedule_tightness, 0.47)
        self.assertEqual(profile.novelty_preference, 0.53)
        self.assertEqual(profile.comfort_preference, 0.59)
        self.assertEqual(profile.category_preferences["restaurant"], 0.47)
        self.assertIn("poi_004", profile.liked_poi_ids)
        self.assertIn("poi_012", profile.disliked_poi_ids)
        self.assertIn("less_walking", profile.common_adjust_actions)


if __name__ == "__main__":
    unittest.main()
