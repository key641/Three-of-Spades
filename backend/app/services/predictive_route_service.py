import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.agent.intent_enhancer import normalize_preferences
from app.schemas.intent import Intent
from app.schemas.route import Route, RoutePlanRequest, RoutePlanResponse
from app.schemas.user import UserProfile
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_service import RouteService
from app.services.strategy_service import StrategyService


class PredictiveRouteRequest(BaseModel):
    user_id: str = "user_demo"
    city: str = "上海"
    weather_scenario: str | None = None
    start_time: str = "10:00"
    duration_hours: int = 5
    start_lat: float | None = None
    start_lng: float | None = None
    user_profile: UserProfile | None = None


class PredictiveRouteService:
    """B-owned weather/profile pre-route generator."""

    ALL_OBJECTIVES = ["photo_food", "food_first", "nature_relax", "photo_citywalk", "indoor_rainy", "night_friendly", "low_walking", "budget", "balanced"]
    FALLBACK_OBJECTIVES = ["photo_citywalk", "food_first", "indoor_rainy", "low_walking", "nature_relax", "night_friendly", "budget"]

    def __init__(
        self,
        weather_path: Path | None = None,
        profile_service: ProfileService | None = None,
        poi_service: POIService | None = None,
        route_service: RouteService | None = None,
        strategy_service: StrategyService | None = None,
    ) -> None:
        self.weather_path = weather_path or Path(__file__).resolve().parents[3] / "data" / "seed" / "mock_weather.json"
        self.weather_payload = self._load_weather()
        self.profile_service = profile_service or ProfileService()
        self.poi_service = poi_service or POIService()
        self.route_service = route_service or RouteService()
        self.strategy_service = strategy_service or StrategyService()

    def generate(self, request: PredictiveRouteRequest) -> RoutePlanResponse:
        weather = self.weather_for(request.city, request.weather_scenario)
        weather_preferences = self.preferences_from_weather(weather)
        profile = self._profile_for_request(request)
        has_profile = profile is not None
        planning_profile = profile or UserProfile(
            user_id=request.user_id,
            tags=[],
            preferences=[],
            avoid_tags=[],
            preference_weights=ProfileService.DEFAULT_WEIGHTS,
        )
        intent = self._intent_for_request(request, planning_profile if has_profile else None, weather_preferences)
        strategy_tags = self.strategy_service.infer_tags(" ".join(intent.preferences), intent, planning_profile)
        strategy_weights = self.profile_service.build_strategy_weights(intent, planning_profile, strategy_tags)
        pois = self.poi_service.search(intent, user_profile=planning_profile, strategy_tags=strategy_tags, limit=48)
        plan_request = RoutePlanRequest(
            intent=intent,
            user_profile=planning_profile,
            strategy_weights=strategy_weights,
            strategy_tags=strategy_tags,
            candidate_pois=pois,
        )

        if has_profile:
            objectives = self._profile_objectives(planning_profile, weather_preferences, pois)
            candidates = self.route_service.generate_routes_for_objectives(
                plan_request,
                objectives,
                max_stops=self._max_stops(intent, weather, planning_profile),
                routes_per_objective=3,
            ).routes
            return RoutePlanResponse(routes=self._select_profile_routes(candidates, objectives))

        candidates = self.route_service.generate_routes_for_objectives(
            plan_request,
            self.ALL_OBJECTIVES,
            max_stops=self._max_stops(intent, weather, planning_profile),
            routes_per_objective=3,
        ).routes
        return RoutePlanResponse(routes=self._select_top_diverse_routes(candidates))

    def weather_for(self, city: str, scenario: str | None = None) -> dict[str, Any]:
        city_weather = self.weather_payload.get("cities", {}).get(city) or self.weather_payload.get("cities", {}).get("上海", {})
        if not city_weather:
            return {}
        if scenario and scenario in city_weather:
            return city_weather[scenario]
        return city_weather.get("sunny") or next(iter(city_weather.values()))

    def preferences_from_weather(self, weather: dict[str, Any]) -> list[str]:
        preferences = list(weather.get("suggested_preferences") or [])
        condition = str(weather.get("condition", ""))
        rain_probability = float(weather.get("rain_probability") or 0)
        temperature = float(weather.get("temperature_c") or 24)
        wind_level = float(weather.get("wind_level") or 0)
        if rain_probability >= 0.55 or "rain" in condition or wind_level >= 5:
            preferences.extend(["室内", "雨天", "少走路"])
        if temperature >= 32:
            preferences.extend(["室内", "少走路", "咖啡"])
        if condition in {"sunny", "cloudy"} and rain_probability < 0.35 and temperature < 32:
            preferences.extend(["citywalk", "拍照", "自然风景"])
        if "night" in condition:
            preferences.extend(["晚上", "夜景"])
        return self._unique(preferences)

    def _profile_for_request(self, request: PredictiveRouteRequest) -> UserProfile | None:
        if request.user_profile and (request.user_profile.tags or request.user_profile.preferences or request.user_profile.preference_weights):
            return request.user_profile
        return self.profile_service.get_seed_profile(request.user_id)

    def _intent_for_request(self, request: PredictiveRouteRequest, profile: UserProfile | None, weather_preferences: list[str]) -> Intent:
        profile_preferences = normalize_preferences([*(profile.preferences if profile else []), *(profile.tags if profile else [])])
        preferences = self._unique([*weather_preferences, *profile_preferences])
        avoid_tags = profile.avoid_tags if profile else []
        return Intent(
            city=request.city,
            start_time=request.start_time,
            duration_hours=request.duration_hours,
            budget_per_person=300,
            preferences=preferences,
            avoid_tags=avoid_tags,
            start_lat=request.start_lat,
            start_lng=request.start_lng,
            scenario="friends_citywalk",
        )

    def _profile_objectives(self, profile: UserProfile, weather_preferences: list[str], pois: list) -> list[str]:
        profile_intent = Intent(preferences=normalize_preferences([*profile.preferences, *profile.tags]))
        profile_tags = self.strategy_service.infer_tags(" ".join(profile_intent.preferences), profile_intent, profile)
        scores = self.strategy_service.objective_scores(profile_tags, profile, self._objective_data_counts(pois))
        selected = [objective for objective, score in sorted(scores.items(), key=lambda item: item[1], reverse=True) if objective != "balanced" and score > 0][:2]
        if len(selected) < 2:
            selected.extend(objective for objective in self._weather_objectives(weather_preferences) if objective not in selected)
        selected.extend(objective for objective in self.FALLBACK_OBJECTIVES if len(selected) < 2 and objective not in selected)
        return [*selected[:2], "balanced"]

    def _weather_objectives(self, preferences: list[str]) -> list[str]:
        terms = set(preferences)
        objectives: list[str] = []
        if {"室内", "雨天"} & terms:
            objectives.append("indoor_rainy")
        if {"少走路", "亲子友好", "老人友好"} & terms:
            objectives.append("low_walking")
        if {"citywalk", "拍照"} & terms:
            objectives.append("photo_citywalk")
        if {"自然风景"} & terms:
            objectives.append("nature_relax")
        if {"晚上", "夜景"} & terms:
            objectives.append("night_friendly")
        if {"吃好", "咖啡"} & terms:
            objectives.append("food_first")
        return objectives

    def _select_profile_routes(self, candidates: list[Route], objectives: list[str]) -> list[Route]:
        selected: list[Route] = []
        for objective in [objective for objective in objectives if objective != "balanced"]:
            self._append_best_diverse(selected, [route for route in candidates if route.objective == objective])
        balanced_candidates = [route for route in candidates if route.objective == "balanced"]
        if balanced_candidates:
            self._append_best_diverse(selected, balanced_candidates, force=True)
        if len(selected) < 3:
            self._append_fillers(selected, candidates)
        return selected[:3]

    def _select_top_diverse_routes(self, candidates: list[Route]) -> list[Route]:
        selected: list[Route] = []
        self._append_fillers(selected, sorted(candidates, key=lambda route: route.score, reverse=True))
        return selected[:3]

    def _append_fillers(self, selected: list[Route], candidates: list[Route]) -> None:
        for threshold in [0.5, 0.7, 1.0]:
            for candidate in sorted(candidates, key=lambda route: route.score, reverse=True):
                if len(selected) >= 3:
                    return
                if self._can_add_route(selected, candidate, threshold):
                    selected.append(candidate)

    def _append_best_diverse(self, selected: list[Route], candidates: list[Route], force: bool = False) -> None:
        if not candidates:
            return
        for threshold in [0.5, 0.7, 1.0]:
            for candidate in sorted(candidates, key=lambda route: route.score, reverse=True):
                if self._can_add_route(selected, candidate, threshold):
                    selected.append(candidate)
                    return
        if force and not any(route.objective == candidates[0].objective for route in selected):
            selected.append(sorted(candidates, key=lambda route: route.score, reverse=True)[0])

    def _can_add_route(self, selected: list[Route], candidate: Route, threshold: float) -> bool:
        candidate_ids = self._route_poi_ids(candidate)
        if not candidate_ids:
            return False
        if any(route.objective == candidate.objective for route in selected):
            return False
        if any(candidate_ids == self._route_poi_ids(route) for route in selected):
            return False
        for route in selected:
            overlap = len(candidate_ids & self._route_poi_ids(route))
            denominator = max(1, min(len(candidate_ids), len(route.stops)))
            if overlap / denominator > threshold:
                return False
            if len(candidate_ids) <= 2 and overlap > 1:
                return False
        return True

    def _route_poi_ids(self, route: Route) -> set[str]:
        return {stop.poi_id for stop in route.stops}

    def _unique(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            normalized = value.strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result

    def _max_stops(self, intent: Intent, weather: dict[str, Any], profile: UserProfile) -> int:
        terms = set(intent.preferences + profile.preferences + profile.tags)
        if intent.duration_hours <= 3 or {"少走路", "亲子友好", "老人友好", "室内"} & terms or float(weather.get("rain_probability") or 0) >= 0.55:
            return 3
        return 4

    def _objective_data_counts(self, pois: list) -> dict[str, int]:
        counts = {objective: 0 for objective in self.ALL_OBJECTIVES}
        for poi in pois:
            text = " ".join([poi.category, poi.primary_category, poi.meal_type, *poi.route_roles, *poi.tags, *poi.secondary_categories])
            if poi.category in {"restaurant", "cafe", "market"} or poi.meal_type != "non_meal":
                counts["food_first"] += 1
            if poi.category in {"restaurant", "cafe", "market"} and ("拍照" in text or "photo" in text):
                counts["photo_food"] += 1
            if poi.category == "park" or poi.primary_category == "nature" or "自然" in text:
                counts["nature_relax"] += 1
            if "photo_stop" in poi.route_roles or "拍照" in text or "citywalk" in text:
                counts["photo_citywalk"] += 1
            if poi.indoor or "室内" in text:
                counts["indoor_rainy"] += 1
            if poi.night_activity >= 0.7 or "night" in text or "夜景" in text:
                counts["night_friendly"] += 1
            if poi.walking_intensity == "low" or "transit_anchor" in poi.route_roles:
                counts["low_walking"] += 1
            if poi.avg_price <= 80 or poi.budget_friendly >= 0.8:
                counts["budget"] += 1
            counts["balanced"] += 1
        return counts

    def _load_weather(self) -> dict[str, Any]:
        with self.weather_path.open(encoding="utf-8") as file:
            return json.load(file)
