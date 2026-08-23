from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.route import Route, RouteStop


class ParsedReplanEvent(BaseModel):
    event_type: str
    event_label: str
    selected_route_id: str | None = None
    current_poi_id: str | None = None
    event_payload: dict[str, Any] = Field(default_factory=dict)


class ReplanIntentParser:
    """Parses local replanning requests into ReplanService event fields."""

    def parse(self, message: str, routes: list[Route]) -> ParsedReplanEvent | None:
        text = message.strip()
        if not text or not routes:
            return None

        route = self._target_route(text, routes)
        target_stop = self._target_stop(text, route)
        payload: dict[str, Any] = {"event_label": text}
        if target_stop:
            payload["affected_poi_id"] = target_stop.poi_id

        queue_minutes = self._queue_minutes(text)
        if queue_minutes is not None:
            payload.update(
                {
                    "queue_minutes": queue_minutes,
                    "avoid_tags": ["排队久"],
                    "prefer_tags": ["少排队"],
                }
            )
            if target_stop and self._is_food_stop(target_stop):
                payload["replacement_category"] = target_stop.category
            return self._event("queue_spike", text, route, target_stop, payload)

        if any(term in text for term in ["下雨", "雨天", "暴雨"]):
            payload.update({"prefer_tags": ["室内"], "avoid_tags": ["步行多"]})
            return self._event("weather_change", text, route, target_stop, payload)

        if any(term in text for term in ["堵车", "交通堵", "路上堵", "临时堵"]):
            payload.update({"traffic_multiplier": 1.6, "event_type": "traffic_jam"})
            return self._event("traffic_jam", text, route, target_stop, payload)

        if any(term in text for term in ["关门", "闭店", "临时关闭", "不开门"]):
            payload.update({"status": "closed", "event_type": "poi_closed", "force_replace": True})
            return self._event("poi_closed", text, route, target_stop, payload)

        if any(term in text for term in ["太累", "累了", "走不动", "少走"]):
            payload.update({"prefer_tags": ["少走路", "室内休息"], "avoid_tags": ["步行多"]})
            return self._event("user_tired", text, route, target_stop, payload)

        if self._looks_like_replace_request(text):
            payload.update({"force_replace": True})
            if target_stop:
                payload["replacement_category"] = target_stop.category
            if any(term in text for term in ["太贵", "贵了", "预算"]):
                payload["avoid_tags"] = ["太贵"]
                payload["prefer_tags"] = ["更省钱"]
            return self._event("replace_poi", text, route, target_stop, payload)

        return None

    def _event(
        self,
        event_type: str,
        label: str,
        route: Route,
        stop: RouteStop | None,
        payload: dict[str, Any],
    ) -> ParsedReplanEvent:
        payload.setdefault("event_type", event_type)
        return ParsedReplanEvent(
            event_type=event_type,
            event_label=label,
            selected_route_id=route.route_id,
            current_poi_id=stop.poi_id if stop else None,
            event_payload=payload,
        )

    def _target_route(self, text: str, routes: list[Route]) -> Route:
        for route in routes:
            if route.route_id and route.route_id in text:
                return route
        return routes[0]

    def _target_stop(self, text: str, route: Route) -> RouteStop | None:
        index_match = re.search(r"第\s*([一二三四五六七八九十\d]+)\s*站", text)
        if index_match:
            index = self._cn_number(index_match.group(1)) - 1
            if 0 <= index < len(route.stops):
                return route.stops[index]

        for stop in route.stops:
            if stop.name and stop.name in text:
                return stop

        if any(term in text for term in ["这家", "店", "餐厅", "咖啡", "吃"]):
            food_stop = next((stop for stop in route.stops if self._is_food_stop(stop)), None)
            if food_stop:
                return food_stop

        return route.stops[0] if route.stops else None

    def _queue_minutes(self, text: str) -> int | None:
        match = re.search(r"排队\s*(\d+)\s*分钟", text)
        return int(match.group(1)) if match else None

    def _looks_like_replace_request(self, text: str) -> bool:
        return any(term in text for term in ["换一家", "换个店", "换一个", "换掉", "替换", "不喜欢这家", "不想去"])

    def _is_food_stop(self, stop: RouteStop) -> bool:
        food_terms = {"restaurant", "cafe", "food", "market", "餐厅", "咖啡", "美食", "小吃"}
        return stop.category in food_terms or stop.primary_category in food_terms or bool(food_terms & set(stop.tags))

    def _cn_number(self, value: str) -> int:
        if value.isdigit():
            return int(value)
        mapping = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        return mapping.get(value, 1)
