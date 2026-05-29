import math
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from app.schemas.map import ExternalPOICandidate, ExternalPOIStatus, GeoPoint, LiveLegEstimate


class MapProvider(Protocol):
    source: str

    def get_live_travel_time(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        mode: str = "walk",
        departure_time: str | None = None,
        event_payload: dict[str, Any] | None = None,
    ) -> LiveLegEstimate:
        ...

    def get_route_options(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        modes: list[str],
        event_payload: dict[str, Any] | None = None,
    ) -> list[LiveLegEstimate]:
        ...

    def search_nearby_pois(
        self,
        location: GeoPoint,
        radius_km: float,
        categories: list[str],
        keywords: list[str],
        event_payload: dict[str, Any] | None = None,
    ) -> list[ExternalPOICandidate]:
        ...

    def get_place_status(self, place_id: str, event_payload: dict[str, Any] | None = None) -> ExternalPOIStatus:
        ...

    def geocode(self, address: str) -> GeoPoint | None:
        ...

    def reverse_geocode(self, lat: float, lng: float) -> str:
        ...


class MockMapProvider:
    """Provider-shaped mock so route logic can later swap in AMap/Baidu/Google."""

    source = "mock"
    QUEUE_CACHE_SECONDS = 120
    _queue_cache: dict[tuple[str, int, str], tuple[int, float]] = {}

    def get_live_travel_time(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        mode: str = "walk",
        departure_time: str | None = None,
        event_payload: dict[str, Any] | None = None,
    ) -> LiveLegEstimate:
        distance = self._distance_km(origin, destination)
        base_minutes = self._base_travel_minutes(distance, mode)
        multiplier = float((event_payload or {}).get("traffic_multiplier", 1.0) or 1.0)
        status = "congested" if multiplier >= 1.4 else "normal"
        return LiveLegEstimate(
            distance_km=round(distance, 1),
            travel_minutes=max(1, round(base_minutes * multiplier)),
            traffic_multiplier=multiplier,
            status=status,
            transport_mode=mode,
            updated_at=self._now(),
            source=self.source,
            reason="交通拥堵，预计通行时间上升" if status == "congested" else "",
        )

    def get_route_options(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        modes: list[str],
        event_payload: dict[str, Any] | None = None,
    ) -> list[LiveLegEstimate]:
        return [
            self.get_live_travel_time(origin, destination, mode=mode, event_payload=event_payload)
            for mode in (modes or ["walk"])
        ]

    def search_nearby_pois(
        self,
        location: GeoPoint,
        radius_km: float,
        categories: list[str],
        keywords: list[str],
        event_payload: dict[str, Any] | None = None,
    ) -> list[ExternalPOICandidate]:
        if not (event_payload or {}).get("allow_external_candidates"):
            return []
        category = categories[0] if categories else "landmark"
        keyword = keywords[0] if keywords else "附近替代点"
        return [
            ExternalPOICandidate(
                external_place_ids={self.source: f"mock_{category}_{abs(hash(keyword)) % 10000}"},
                source_provider=self.source,
                name=f"{keyword}替代点",
                lat=location.lat + 0.004,
                lng=location.lng + 0.004,
                map_category=category,
                avg_price=80 if category in {"restaurant", "cafe", "food"} else 0,
                rating=4.3,
                review_count=120,
                queue_minutes=8,
                live_crowd_level=0.25,
                tags=[keyword, category],
            )
        ]

    def get_place_status(self, place_id: str, event_payload: dict[str, Any] | None = None) -> ExternalPOIStatus:
        payload = event_payload or {}
        affected_ids = set(self._as_list(payload.get("affected_poi_ids")))
        affected_id = str(payload.get("affected_poi_id", ""))
        is_affected = place_id in affected_ids or (affected_id and place_id == affected_id)
        now = datetime.now(UTC).replace(microsecond=0)

        status = str(payload.get("status", "normal"))
        if payload.get("event_type") == "poi_closed" and is_affected:
            status = "closed"
        if status in {"closed", "unavailable", "sold_out"} and is_affected:
            return ExternalPOIStatus(
                place_id=place_id,
                status=status,
                is_open=False,
                is_accessible=False,
                updated_at=self._format_time(now),
                valid_until=self._format_time(now + timedelta(minutes=5)),
                source=self.source,
                reason=str(payload.get("reason") or payload.get("event_label") or "地点暂不可用"),
            )

        queue_minutes = payload.get("queue_minutes")
        crowd_level = payload.get("live_crowd_level")
        if payload.get("event_type") == "queue_spike" and is_affected:
            queue_minutes = queue_minutes or 90
            crowd_level = crowd_level or 0.9
        if queue_minutes is None and payload.get("enable_live_queue_mock", True):
            queue_minutes, crowd_level = self._mock_live_queue(place_id, payload, now)

        return ExternalPOIStatus(
            place_id=place_id,
            queue_minutes=int(queue_minutes) if queue_minutes is not None and (is_affected or payload.get("enable_live_queue_mock", True)) else None,
            live_crowd_level=float(crowd_level) if crowd_level is not None and (is_affected or payload.get("enable_live_queue_mock", True)) else None,
            updated_at=self._format_time(now),
            valid_until=self._format_time(now + timedelta(seconds=self.QUEUE_CACHE_SECONDS)),
            source=self.source,
            reason=str(payload.get("reason") or payload.get("event_label") or "") if is_affected else "",
        )

    def geocode(self, address: str) -> GeoPoint | None:
        return None

    def reverse_geocode(self, lat: float, lng: float) -> str:
        return f"{lat:.5f},{lng:.5f}"

    def _base_travel_minutes(self, distance_km: float, mode: str) -> int:
        if mode == "walk":
            return max(5, round(distance_km * 12))
        if mode in {"metro", "bus"}:
            return round(8 + distance_km * 5)
        return round(10 + distance_km * 4)

    def _distance_km(self, origin: GeoPoint, destination: GeoPoint) -> float:
        radius_km = 6371
        dlat = math.radians(destination.lat - origin.lat)
        dlng = math.radians(destination.lng - origin.lng)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(origin.lat)) * math.cos(math.radians(destination.lat)) * math.sin(dlng / 2) ** 2
        )
        return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _now(self) -> str:
        return self._format_time(datetime.now(UTC).replace(microsecond=0))

    def _format_time(self, value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    def _mock_live_queue(self, place_id: str, payload: dict[str, Any], now: datetime) -> tuple[int, float]:
        base_queue = int(payload.get("base_queue_minutes") or payload.get("queue_time_min") or 0)
        category = str(payload.get("category") or payload.get("primary_category") or "")
        seed = str(payload.get("session_id") or payload.get("seed") or "demo")
        bucket = int(now.timestamp() // self.QUEUE_CACHE_SECONDS)
        cache_key = (place_id, bucket, seed)
        cached = self._queue_cache.get(cache_key)
        if cached:
            return cached

        hour = now.hour
        category_bonus = 0
        if category in {"restaurant", "food"} and (11 <= hour <= 13 or 17 <= hour <= 20):
            category_bonus = 14
        elif category in {"cafe"} and 14 <= hour <= 17:
            category_bonus = 8
        elif category in {"landmark", "scenic", "gallery", "museum", "culture"} and 16 <= hour <= 20:
            category_bonus = 6

        stable_noise = abs(hash(f"{place_id}:{bucket}:{seed}")) % 13 - 4
        queue = max(0, min(120, base_queue + category_bonus + stable_noise))
        crowd = min(1.0, max(0.05, queue / 90))
        self._queue_cache[cache_key] = (queue, crowd)
        return queue, crowd

    def _as_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]
