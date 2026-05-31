import math
import threading
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lng: float


@dataclass(frozen=True)
class RouteLegStep:
    instruction: str
    distance_meters: int
    duration_minutes: int


@dataclass(frozen=True)
class RouteLeg:
    mode: str
    distance_meters: int
    duration_minutes: int
    polyline: str
    steps: list[RouteLegStep] = field(default_factory=list)
    source: str = "fallback"


class AmapService:
    """A-owned adapter: normalizes Amap route responses for route strategy code."""

    BASE_URL = "https://restapi.amap.com/v3/direction"

    def __init__(self, api_key: str | None = None, timeout_seconds: float = 2.5) -> None:
        self.api_key = settings.amap_web_service_key if api_key is None else api_key
        self.timeout_seconds = timeout_seconds
        self._route_leg_cache: dict[tuple[str, str, str], RouteLeg] = {}
        self._route_leg_cache_lock = threading.Lock()
        self._route_leg_inflight: dict[tuple[str, str, str], threading.Event] = {}

    def route_leg(self, origin: GeoPoint, destination: GeoPoint, mode: str = "walk") -> RouteLeg:
        cache_key = (self._format_point(origin), self._format_point(destination), self._endpoint_mode(mode))
        inflight_event: threading.Event | None = None
        should_fetch = False
        with self._route_leg_cache_lock:
            cached = self._route_leg_cache.get(cache_key)
            if cached is not None:
                return cached
            inflight_event = self._route_leg_inflight.get(cache_key)
            if inflight_event is None:
                inflight_event = threading.Event()
                self._route_leg_inflight[cache_key] = inflight_event
                should_fetch = True

        if not should_fetch:
            inflight_event.wait()
            with self._route_leg_cache_lock:
                cached = self._route_leg_cache.get(cache_key)
            if cached is not None:
                return cached
            return self._fallback_leg(origin, destination, mode)

        if not self.api_key:
            leg = self._fallback_leg(origin, destination, mode)
            self._store_route_leg(cache_key, leg)
            return leg

        endpoint_mode = self._endpoint_mode(mode)
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(
                    f"{self.BASE_URL}/{endpoint_mode}",
                    params={
                        "key": self.api_key,
                        "origin": self._format_point(origin),
                        "destination": self._format_point(destination),
                        "extensions": "base",
                    },
                )
            response.raise_for_status()
            data = response.json()
            leg = self._parse_route_response(data, mode)
            result = leg or self._fallback_leg(origin, destination, mode)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            result = self._fallback_leg(origin, destination, mode)
        self._store_route_leg(cache_key, result)
        return result

    def _store_route_leg(self, cache_key: tuple[str, str, str], leg: RouteLeg) -> None:
        with self._route_leg_cache_lock:
            self._route_leg_cache[cache_key] = leg
            inflight_event = self._route_leg_inflight.pop(cache_key, None)
            if inflight_event is not None:
                inflight_event.set()

    def _parse_route_response(self, data: dict[str, Any], mode: str) -> RouteLeg | None:
        if data.get("status") != "1":
            return None
        paths = data.get("route", {}).get("paths") or []
        if not paths:
            return None

        path = paths[0]
        distance_meters = self._coerce_int(path.get("distance"))
        duration_seconds = self._coerce_int(path.get("duration"))
        steps = self._parse_steps(path.get("steps") or [])
        polyline = self._join_step_polylines(path.get("steps") or [])
        if distance_meters <= 0 or duration_seconds <= 0:
            return None
        return RouteLeg(
            mode=mode,
            distance_meters=distance_meters,
            duration_minutes=max(1, round(duration_seconds / 60)),
            polyline=polyline,
            steps=steps,
            source="amap",
        )

    def _parse_steps(self, raw_steps: list[dict[str, Any]]) -> list[RouteLegStep]:
        steps: list[RouteLegStep] = []
        for step in raw_steps:
            distance = self._coerce_int(step.get("distance"))
            duration = self._coerce_int(step.get("duration"))
            steps.append(
                RouteLegStep(
                    instruction=str(step.get("instruction") or ""),
                    distance_meters=distance,
                    duration_minutes=max(1, round(duration / 60)) if duration > 0 else 0,
                )
            )
        return steps

    def _fallback_leg(self, origin: GeoPoint, destination: GeoPoint, mode: str) -> RouteLeg:
        distance_km = self._distance_km(origin, destination)
        distance_meters = max(1, round(distance_km * 1000))
        duration_minutes = self._fallback_duration_minutes(distance_km, mode)
        return RouteLeg(
            mode=mode,
            distance_meters=distance_meters,
            duration_minutes=duration_minutes,
            polyline=f"{self._format_point(origin)};{self._format_point(destination)}",
            source="fallback",
        )

    def _fallback_duration_minutes(self, distance_km: float, mode: str) -> int:
        if "walk" in mode:
            return max(5, round(distance_km * 12))
        if "bike" in mode:
            return max(4, round(distance_km * 5))
        if "drive" in mode or "taxi" in mode:
            return max(8, round(6 + distance_km * 3))
        return max(8, round(8 + distance_km * 5))

    def _endpoint_mode(self, mode: str) -> str:
        if "drive" in mode or "taxi" in mode:
            return "driving"
        return "walking"

    def _join_step_polylines(self, raw_steps: list[dict[str, Any]]) -> str:
        parts = [str(step.get("polyline") or "").strip() for step in raw_steps]
        return ";".join(part for part in parts if part)

    def _coerce_int(self, value: Any) -> int:
        if value is None or value == "":
            return 0
        return int(float(value))

    def _format_point(self, point: GeoPoint) -> str:
        return f"{point.lng},{point.lat}"

    def _distance_km(self, origin: GeoPoint, destination: GeoPoint) -> float:
        radius_km = 6371
        dlat = math.radians(destination.lat - origin.lat)
        dlng = math.radians(destination.lng - origin.lng)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(origin.lat)) * math.cos(math.radians(destination.lat)) * math.sin(dlng / 2) ** 2
        )
        return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
