from dataclasses import dataclass

from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.user import StrategyTag, StrategyWeights, UserProfile


@dataclass(frozen=True)
class StrategyTagRule:
    aliases: tuple[str, ...]
    multipliers: dict[str, float]
    objectives: dict[str, float]


class StrategyService:
    """B-owned strategy rules: tag intensity, multiplicative weights, and objective scoring."""

    GAMMA = 1.4
    BOUNDS = {
        "quality": (0.12, 0.42),
        "queue": (0.08, 0.40),
        "distance": (0.08, 0.38),
        "budget": (0.05, 0.35),
        "preference": (0.10, 0.45),
    }
    RULES: dict[str, StrategyTagRule] = {
        "photo": StrategyTagRule(("拍照", "出片", "打卡", "好看", "网红"), {"preference": 1.55, "quality": 1.15}, {"photo_citywalk": 0.65}),
        "photo_food": StrategyTagRule(("饭店拍照", "餐厅环境", "餐厅好看", "饭店好看", "拍照吃饭"), {"preference": 1.9, "quality": 1.3, "queue": 0.92}, {"photo_food": 1.5, "food_first": 0.55}),
        "food_first": StrategyTagRule(("美食", "吃好", "好吃", "餐厅", "吃饭", "小吃"), {"preference": 1.65, "quality": 1.18}, {"food_first": 0.9}),
        "nature": StrategyTagRule(("自然", "风景", "自然风景", "公园", "江景", "海边", "湖边", "山", "森林"), {"preference": 1.55, "distance": 1.12}, {"nature_relax": 1.0, "photo_citywalk": 0.4}),
        "quiet": StrategyTagRule(("安静", "清净", "人少"), {"queue": 1.25, "preference": 1.25}, {"balanced": 0.25, "nature_relax": 0.35}),
        "low_walking": StrategyTagRule(("少走路", "轻松", "别太累", "不累", "老人", "长辈"), {"distance": 1.45, "queue": 1.08}, {"low_walking": 0.85}),
        "budget": StrategyTagRule(("省钱", "便宜", "性价比", "高性价比", "预算低"), {"budget": 1.6, "quality": 0.95}, {"budget": 0.85}),
        "indoor_rainy": StrategyTagRule(("室内", "雨天", "下雨"), {"preference": 1.45, "distance": 1.12}, {"indoor_rainy": 0.95}),
        "night_view": StrategyTagRule(("晚上", "夜景", "夜游", "今晚"), {"preference": 1.5}, {"night_friendly": 0.95}),
        "local_vibe": StrategyTagRule(("本地", "市井", "地道", "老字号", "本地感"), {"preference": 1.45}, {"food_first": 0.4, "photo_citywalk": 0.35}),
        "family": StrategyTagRule(("亲子", "带娃", "小朋友", "儿童"), {"distance": 1.3, "queue": 1.15, "quality": 1.12}, {"low_walking": 0.45, "indoor_rainy": 0.35}),
        "elderly": StrategyTagRule(("老人", "长辈", "父母"), {"distance": 1.45, "queue": 1.15, "quality": 1.12}, {"low_walking": 0.75}),
        "low_queue": StrategyTagRule(("少排队", "别排队", "不排队", "排队少"), {"queue": 1.4, "quality": 0.95}, {}),
        "cafe": StrategyTagRule(("咖啡", "下午茶"), {"preference": 1.4}, {"food_first": 0.35, "photo_citywalk": 0.25}),
        "art_exhibition": StrategyTagRule(("艺术展", "展览", "美术馆", "博物馆"), {"preference": 1.45, "quality": 1.1}, {"photo_citywalk": 0.45, "indoor_rainy": 0.35}),
    }

    def infer_tags(self, message: str, intent: Intent, profile: UserProfile) -> list[StrategyTag]:
        text = " ".join([message, *intent.interest_tags, *intent.optimization_goals])
        tags: dict[str, StrategyTag] = {}
        for tag, rule in self.RULES.items():
            evidence = self._first_hit(text, rule.aliases)
            if evidence:
                tags[tag] = StrategyTag(tag=tag, intensity=self._intensity(message, evidence, tag), evidence=evidence)

        if "photo" in tags and "food_first" in tags:
            explicit_evidence = self._first_hit(message, self.RULES["photo_food"].aliases)
            if explicit_evidence:
                intensity = max(self._intensity(message, explicit_evidence, "photo_food"), 0.85)
                evidence = explicit_evidence
            else:
                intensity = min(max(tags["photo"].intensity, tags["food_first"].intensity) * 0.62, 0.55)
                evidence = "拍照+美食"
            tags["photo_food"] = StrategyTag(tag="photo_food", intensity=intensity, evidence=evidence)

        for term in profile.interest_tags + profile.optimization_goals + profile.tags + profile.preferences:
            for tag, rule in self.RULES.items():
                if tag in tags:
                    continue
                if term in rule.aliases:
                    tags[tag] = StrategyTag(tag=tag, intensity=0.35, evidence=f"画像:{term}")
        return sorted(tags.values(), key=lambda item: item.intensity, reverse=True)

    def build_weights(self, base: StrategyWeights, strategy_tags: list[StrategyTag]) -> StrategyWeights:
        if not strategy_tags:
            return base
        values = base.model_dump()
        for strategy_tag in strategy_tags:
            rule = self.RULES.get(strategy_tag.tag)
            if not rule:
                continue
            intensity = self._clamp(strategy_tag.intensity)
            curve = intensity**self.GAMMA
            for dimension, max_multiplier in rule.multipliers.items():
                current = values.get(dimension, 0)
                if max_multiplier >= 1:
                    multiplier = 1 + (max_multiplier - 1) * curve
                else:
                    multiplier = 1 - (1 - max_multiplier) * curve
                values[dimension] = current * multiplier
        values = {key: self._bounded(key, value) for key, value in values.items()}
        return StrategyWeights(**self._normalize(values))

    def tag_score(self, poi: POI, strategy_tags: list[StrategyTag]) -> float:
        if not strategy_tags:
            return 0
        score = 0.0
        for strategy_tag in strategy_tags:
            if strategy_tag.polarity != "prefer":
                continue
            match = self._poi_tag_match(poi, strategy_tag.tag)
            score += match * self._clamp(strategy_tag.intensity)
        return score / max(len(strategy_tags), 1)

    def objective_scores(self, strategy_tags: list[StrategyTag], profile: UserProfile, data_counts: dict[str, int]) -> dict[str, float]:
        scores = {objective: 0.0 for objective in ["photo_food", "food_first", "nature_relax", "photo_citywalk", "indoor_rainy", "night_friendly", "low_walking", "budget", "balanced"]}
        for strategy_tag in strategy_tags:
            rule = self.RULES.get(strategy_tag.tag)
            if not rule:
                continue
            for objective, affinity in rule.objectives.items():
                scores[objective] = scores.get(objective, 0) + affinity * strategy_tag.intensity * 0.8
        profile_terms = set(profile.interest_tags + profile.optimization_goals + profile.tags + profile.preferences)
        if "美食" in profile_terms:
            scores["food_first"] += 0.12
        if "citywalk" in profile_terms or "拍照" in profile_terms:
            scores["photo_citywalk"] += 0.12
        if "少走路" in profile_terms:
            scores["low_walking"] += 0.08
        for objective, count in data_counts.items():
            scores[objective] = scores.get(objective, 0) + min(count / 12, 1) * 0.08
        scores["balanced"] += 0.2
        return scores

    def _poi_tag_match(self, poi: POI, tag: str) -> float:
        text = self._poi_text(poi)
        if tag == "photo_food":
            food = poi.category in {"restaurant", "market", "cafe"} or poi.meal_type != "non_meal"
            photo = self._contains(text, ("拍照", "出片", "好看", "文艺", "经典", "环境", "photo"))
            return 1.0 if food and photo else 0.35 if food else 0.0
        if tag == "nature":
            return 1.0 if poi.category == "park" or self._contains(text, ("自然", "风景", "公园", "江景", "海边", "湖", "森林", "nature")) else 0.0
        if tag == "quiet":
            return max(0.0, 1 - poi.queue_minutes / 30) if self._contains(text, ("安静", "人少", "小众")) or poi.queue_minutes <= 8 else 0.0
        rule = self.RULES.get(tag)
        return 1.0 if rule and self._contains(text, rule.aliases) else 0.0

    def _intensity(self, message: str, evidence: str, tag: str) -> float:
        if evidence.startswith("画像:"):
            return 0.35

        window = self._evidence_window(message, evidence)
        target_text = window or message
        if tag == "indoor_rainy" and self._contains(message, ("不希望一直在室外", "不想一直在室外", "不要一直在室外", "别一直在室外", "不全在室外")):
            return 0.88
        if self._contains(target_text, ("必须", "一定", "最重要", "核心", "必须要")):
            return 1.0
        if self._contains(target_text, ("最好", "很想", "特别", "主要")):
            return 0.85

        base_by_tag = {
            "photo": 0.58,
            "food_first": 0.56,
            "indoor_rainy": 0.62,
            "photo_food": 0.55,
            "cafe": 0.54,
        }
        intensity = base_by_tag.get(tag, 0.48)

        if self._contains(target_text, ("希望", "想", "可以", "能够", "适合")):
            intensity += 0.08
        if self._contains(target_text, ("还能", "顺便", "吃点", "一点", "稍微")):
            intensity -= 0.08
        if tag == "food_first" and self._contains(target_text, ("吃点", "小吃", "特色美食")):
            intensity -= 0.06
        if tag == "photo" and self._contains(target_text, ("打卡", "出片")):
            intensity += 0.04
        if tag == "photo_food" and not self._contains(message, self.RULES["photo_food"].aliases):
            intensity -= 0.12

        return self._clamp(round(intensity, 2))

    def _evidence_window(self, message: str, evidence: str, radius: int = 8) -> str:
        index = message.find(evidence)
        if index < 0:
            return ""
        start = max(0, index - radius)
        end = min(len(message), index + len(evidence) + radius)
        return message[start:end]

    def _first_hit(self, text: str, aliases: tuple[str, ...]) -> str:
        return next((alias for alias in aliases if alias in text), "")

    def _contains(self, text: str, aliases: tuple[str, ...]) -> bool:
        lowered = text.lower()
        return any(alias.lower() in lowered for alias in aliases)

    def _poi_text(self, poi: POI) -> str:
        return " ".join(
            str(part)
            for part in [
                poi.name,
                poi.category,
                poi.primary_category,
                poi.meal_type,
                poi.highlight_text,
                poi.ugc_tip,
                *poi.secondary_categories,
                *poi.route_roles,
                *poi.experience_tags,
                *poi.tags,
                *poi.highlight_text_tags,
                *poi.suitable_time_slots,
            ]
            if part
        )

    def _bounded(self, key: str, value: float) -> float:
        minimum, maximum = self.BOUNDS[key]
        return max(minimum, min(maximum, value))

    def _normalize(self, values: dict[str, float]) -> dict[str, float]:
        total = sum(values.values()) or 1
        return {key: value / total for key, value in values.items()}

    def _clamp(self, value: float) -> float:
        return max(0, min(1, value))
