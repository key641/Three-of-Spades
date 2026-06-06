import unittest

from app.agent.tag_taxonomy import extract_tag_layers, split_preference_terms
from app.schemas.intent import Intent


class TagTaxonomyTest(unittest.TestCase):
    def test_splits_legacy_preferences_into_layers(self) -> None:
        layers = split_preference_terms(["拍照", "更省钱", "少排队"])

        self.assertEqual(layers.interest_tags, ["拍照"])
        self.assertEqual(layers.optimization_goals, ["省钱", "少排队"])
        self.assertEqual(layers.avoid_tags, [])

    def test_message_splits_interest_and_optimization(self) -> None:
        layers = extract_tag_layers("想拍照和吃美食，少排队一点")

        self.assertEqual(layers.interest_tags, ["美食", "拍照"])
        self.assertEqual(layers.optimization_goals, ["少排队"])
        self.assertEqual(layers.avoid_tags, [])

    def test_optimization_goals_do_not_become_interest_tags(self) -> None:
        layers = extract_tag_layers("更省钱、少走路、轻松点")

        self.assertEqual(layers.interest_tags, [])
        self.assertEqual(layers.optimization_goals, ["省钱", "少走路", "轻松"])

    def test_explicit_budget_is_not_tagged_as_saving_money(self) -> None:
        layers = extract_tag_layers("人均100以内")

        self.assertEqual(layers.interest_tags, [])
        self.assertEqual(layers.optimization_goals, [])
        self.assertEqual(layers.avoid_tags, [])

    def test_negative_photo_goes_to_avoid_tags(self) -> None:
        layers = extract_tag_layers("不想拍照")

        self.assertEqual(layers.interest_tags, [])
        self.assertEqual(layers.avoid_tags, ["拍照打卡"])

    def test_intent_keeps_legacy_preferences_compatible(self) -> None:
        intent = Intent(preferences=["打卡", "别排队", "高性价比"], avoid_tags=["人多"])

        self.assertEqual(intent.interest_tags, ["拍照"])
        self.assertEqual(intent.optimization_goals, ["少排队", "高性价比"])
        self.assertEqual(intent.preferences, ["拍照", "少排队", "高性价比"])
        self.assertEqual(intent.avoid_tags, ["人流密集"])


if __name__ == "__main__":
    unittest.main()
