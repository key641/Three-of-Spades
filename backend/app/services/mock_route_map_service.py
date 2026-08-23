from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from app.services.amap_service import GeoPoint, RouteLeg, RouteLegStep


class MockRouteMapService:
    """High-fidelity mock map router for stable demo route legs."""

    source = "mock_map"
    MAX_SYNTHETIC_ACCESS_KM = 1.8
    MAX_SYNTHETIC_EGRESS_KM = 1.8

    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path or Path(__file__).resolve().parents[3] / "data" / "seed" / "mock_map.json"
        with self.data_path.open(encoding="utf-8") as file:
            self.payload = json.load(file)
        self.defaults = self.payload.get("defaults", {})
        self.cities = self.payload.get("cities", {})

    def route_leg(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        mode: str = "walk",
        departure_time: str | None = None,
    ) -> RouteLeg:
        normalized_mode = self._normalize_mode(mode)
        city_name, city = self._nearest_city(origin, destination)
        if normalized_mode == "metro":
            return self._metro_leg(origin, destination, city_name, city, departure_time) or self._synthetic_transit_leg(origin, destination, city, departure_time, mode="metro")
        if normalized_mode == "bus":
            return self._bus_leg(origin, destination, city_name, city, departure_time) or self._synthetic_transit_leg(origin, destination, city, departure_time, mode="bus")
        if normalized_mode == "taxi":
            return self._taxi_leg(origin, destination, city_name, city, departure_time)
        return self._walk_leg(origin, destination, city_name, city, departure_time)

    def _walk_leg(self, origin: GeoPoint, destination: GeoPoint, city_name: str, city: dict[str, Any], departure_time: str | None) -> RouteLeg:
        distance_meters = self._mode_distance_meters(origin, destination, "walk")
        minutes = self._mode_minutes(distance_meters, "walk", city, departure_time)
        return RouteLeg(
            mode="walk",
            distance_meters=distance_meters,
            duration_minutes=minutes,
            polyline=self._polyline([origin, destination]),
            steps=[
                RouteLegStep(
                    instruction=f"步行约 {self._display_meters(distance_meters)} 米，预计 {minutes} 分钟到达目的地",
                    distance_meters=distance_meters,
                    duration_minutes=minutes,
                )
            ],
            source=self.source,
        )

    def _taxi_leg(self, origin: GeoPoint, destination: GeoPoint, city_name: str, city: dict[str, Any], departure_time: str | None) -> RouteLeg:
        distance_meters = self._mode_distance_meters(origin, destination, "taxi")
        minutes = self._mode_minutes(distance_meters, "taxi", city, departure_time)
        midpoint = self._midpoint(origin, destination, offset=0.003)
        return RouteLeg(
            mode="taxi",
            distance_meters=distance_meters,
            duration_minutes=minutes,
            polyline=self._polyline([origin, midpoint, destination]),
            steps=[
                RouteLegStep(
                    instruction=f"打车约 {self._display_km(distance_meters)} 公里，预计 {minutes} 分钟到达目的地",
                    distance_meters=distance_meters,
                    duration_minutes=minutes,
                )
            ],
            source=self.source,
        )

    def _metro_leg(self, origin: GeoPoint, destination: GeoPoint, city_name: str, city: dict[str, Any], departure_time: str | None) -> RouteLeg | None:
        direct = self._best_direct_line(origin, destination, city.get("metro_lines", []), max_access_km=1.4)
        if direct:
            return self._transit_leg(origin, destination, direct, city, departure_time, mode="metro")

        transfer = self._best_transfer_line(origin, destination, city.get("metro_lines", []), max_access_km=1.4)
        if transfer:
            return self._transfer_metro_leg(origin, destination, transfer, city, departure_time)
        return None

    def _bus_leg(self, origin: GeoPoint, destination: GeoPoint, city_name: str, city: dict[str, Any], departure_time: str | None) -> RouteLeg | None:
        direct = self._best_direct_line(origin, destination, city.get("bus_lines", []), max_access_km=0.9, station_key="stops")
        if direct:
            return self._transit_leg(origin, destination, direct, city, departure_time, mode="bus")
        return None

    def _synthetic_transit_leg(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        city: dict[str, Any],
        departure_time: str | None,
        mode: str,
    ) -> RouteLeg | None:
        station_key = "stations" if mode == "metro" else "stops"
        lines = city.get("metro_lines" if mode == "metro" else "bus_lines", [])
        candidates: list[dict[str, Any]] = []
        for line in lines:
            stations = line.get(station_key, [])
            if len(stations) < 2:
                continue
            start_index, start, start_km = self._nearest_station(origin, stations)
            end_index, end, end_km = self._nearest_station(destination, stations)
            if start_index == end_index:
                continue
            if start_km > self.MAX_SYNTHETIC_ACCESS_KM or end_km > self.MAX_SYNTHETIC_EGRESS_KM:
                continue
            low, high = sorted((start_index, end_index))
            line_points = stations[low : high + 1]
            if start_index > end_index:
                line_points = list(reversed(line_points))
            candidates.append(
                {
                    "line": line,
                    "start": start,
                    "end": end,
                    "start_index": start_index,
                    "end_index": end_index,
                    "line_points": line_points,
                    "score": start_km + end_km + abs(end_index - start_index) * 0.2,
                }
            )
        if not candidates:
            return None
        best = min(candidates, key=lambda item: item["score"])
        return self._transit_leg(origin, destination, best, city, departure_time, mode=mode)

    def _transit_leg(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        match: dict[str, Any],
        city: dict[str, Any],
        departure_time: str | None,
        mode: str,
    ) -> RouteLeg:
        line = match["line"]
        start = match["start"]
        end = match["end"]
        stop_count = abs(match["end_index"] - match["start_index"])
        access_meters = self._mode_distance_meters(origin, self._point(start), "walk")
        egress_meters = self._mode_distance_meters(self._point(end), destination, "walk")
        transit_meters = self._line_distance_meters(match["line_points"], "metro" if mode == "metro" else "bus")
        access_minutes = max(1, self._mode_minutes(access_meters, "walk", city, departure_time))
        egress_minutes = max(1, self._mode_minutes(egress_meters, "walk", city, departure_time))
        walk_minutes = access_minutes + egress_minutes
        ride_minutes = self._mode_minutes(transit_meters, mode, city, departure_time)
        total_minutes = walk_minutes + ride_minutes
        line_label = line["name"]
        verb = "地铁" if mode == "metro" else "公交"
        transit_instruction = self._transit_instruction(verb, line_label, stop_count, end["name"], transit_meters, ride_minutes)
        total_distance = access_meters + transit_meters + egress_meters
        return RouteLeg(
            mode=mode,
            distance_meters=total_distance,
            duration_minutes=total_minutes,
            polyline=self._polyline([origin, self._point(start), *[self._point(point) for point in match["line_points"][1:-1]], self._point(end), destination]),
            steps=[
                RouteLegStep(self._access_instruction(access_meters, access_minutes, start["name"], mode), access_meters, access_minutes),
                RouteLegStep(transit_instruction, transit_meters, ride_minutes),
                RouteLegStep(self._egress_instruction(egress_meters, egress_minutes, mode), egress_meters, egress_minutes),
            ],
            source=self.source,
        )

    def _transfer_metro_leg(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        match: dict[str, Any],
        city: dict[str, Any],
        departure_time: str | None,
    ) -> RouteLeg:
        first = match["first"]
        second = match["second"]
        transfer = match["transfer"]
        start = first["start"]
        end = second["end"]
        access_meters = self._mode_distance_meters(origin, self._point(start), "walk")
        egress_meters = self._mode_distance_meters(self._point(end), destination, "walk")
        first_meters = self._line_distance_meters(first["line_points"], "metro")
        second_meters = self._line_distance_meters(second["line_points"], "metro")
        transfer_minutes = int(self.defaults.get("metro", {}).get("transfer_minutes", 7))
        access_minutes = max(1, self._mode_minutes(access_meters, "walk", city, departure_time))
        egress_minutes = max(1, self._mode_minutes(egress_meters, "walk", city, departure_time))
        first_minutes = self._mode_minutes(first_meters, "metro", city, departure_time)
        second_minutes = self._mode_minutes(second_meters, "metro", city, departure_time)
        walk_minutes = access_minutes + egress_minutes
        ride_minutes = first_minutes + second_minutes + transfer_minutes
        total_distance = access_meters + first_meters + second_meters + egress_meters
        return RouteLeg(
            mode="metro",
            distance_meters=total_distance,
            duration_minutes=walk_minutes + ride_minutes,
            polyline=self._polyline([origin, self._point(start), *[self._point(point) for point in first["line_points"][1:]], *[self._point(point) for point in second["line_points"][1:]], destination]),
            steps=[
                RouteLegStep(self._access_instruction(access_meters, access_minutes, start["name"], "metro"), access_meters, access_minutes),
                RouteLegStep(self._transit_instruction("地铁", first["line"]["name"], abs(first["end_index"] - first["start_index"]), transfer["name"], first_meters, first_minutes), first_meters, first_minutes),
                RouteLegStep(f"在 {transfer['name']} 换乘 {second['line']['name']}", 0, transfer_minutes),
                RouteLegStep(self._transit_instruction("地铁", second["line"]["name"], abs(second["end_index"] - second["start_index"]), end["name"], second_meters, second_minutes), second_meters, second_minutes),
                RouteLegStep(self._egress_instruction(egress_meters, egress_minutes, "metro"), egress_meters, egress_minutes),
            ],
            source=self.source,
        )

    def _best_direct_line(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        lines: list[dict[str, Any]],
        max_access_km: float,
        station_key: str = "stations",
    ) -> dict[str, Any] | None:
        best: dict[str, Any] | None = None
        for line in lines:
            stations = line.get(station_key, [])
            if len(stations) < 2:
                continue
            start_index, start, start_km = self._nearest_station(origin, stations)
            end_index, end, end_km = self._nearest_station(destination, stations)
            if start_index == end_index or start_km > max_access_km or end_km > max_access_km:
                continue
            low, high = sorted((start_index, end_index))
            line_points = stations[low : high + 1]
            if start_index > end_index:
                line_points = list(reversed(line_points))
            score = start_km + end_km + abs(end_index - start_index) * 0.18
            candidate = {
                "line": line,
                "start": start,
                "end": end,
                "start_index": start_index,
                "end_index": end_index,
                "line_points": line_points,
                "score": score,
            }
            if best is None or candidate["score"] < best["score"]:
                best = candidate
        return best

    def _best_transfer_line(self, origin: GeoPoint, destination: GeoPoint, lines: list[dict[str, Any]], max_access_km: float) -> dict[str, Any] | None:
        best: dict[str, Any] | None = None
        for first_line in lines:
            for second_line in lines:
                if first_line is second_line:
                    continue
                common_names = {station["name"] for station in first_line.get("stations", [])} & {station["name"] for station in second_line.get("stations", [])}
                for transfer_name in common_names:
                    first_start_index, first_start, first_start_km = self._nearest_station(origin, first_line.get("stations", []))
                    second_end_index, second_end, second_end_km = self._nearest_station(destination, second_line.get("stations", []))
                    if first_start_km > max_access_km or second_end_km > max_access_km:
                        continue
                    first_transfer_index = self._station_index(first_line.get("stations", []), transfer_name)
                    second_transfer_index = self._station_index(second_line.get("stations", []), transfer_name)
                    if first_transfer_index is None or second_transfer_index is None:
                        continue
                    first = self._line_segment(first_line, first_start_index, first_transfer_index)
                    second = self._line_segment(second_line, second_transfer_index, second_end_index)
                    if not first or not second:
                        continue
                    score = first_start_km + second_end_km + len(first["line_points"]) * 0.18 + len(second["line_points"]) * 0.18 + 1.0
                    candidate = {
                        "first": first,
                        "second": second,
                        "transfer": first["end"],
                        "score": score,
                    }
                    if best is None or score < best["score"]:
                        best = candidate
        return best

    def _line_segment(self, line: dict[str, Any], start_index: int, end_index: int) -> dict[str, Any] | None:
        if start_index == end_index:
            return None
        stations = line.get("stations", [])
        low, high = sorted((start_index, end_index))
        points = stations[low : high + 1]
        if start_index > end_index:
            points = list(reversed(points))
        return {
            "line": line,
            "start": stations[start_index],
            "end": stations[end_index],
            "start_index": start_index,
            "end_index": end_index,
            "line_points": points,
        }

    def _nearest_city(self, origin: GeoPoint, destination: GeoPoint) -> tuple[str, dict[str, Any]]:
        midpoint = self._midpoint(origin, destination)
        city_name = min(
            self.cities,
            key=lambda name: self._distance_km(midpoint, GeoPoint(**self.cities[name]["center"])),
        )
        return city_name, self.cities[city_name]

    def _nearest_station(self, point: GeoPoint, stations: list[dict[str, Any]]) -> tuple[int, dict[str, Any], float]:
        index, station = min(enumerate(stations), key=lambda item: self._distance_km(point, self._point(item[1])))
        return index, station, self._distance_km(point, self._point(station))

    def _station_index(self, stations: list[dict[str, Any]], name: str) -> int | None:
        return next((index for index, station in enumerate(stations) if station["name"] == name), None)

    def _point(self, value: dict[str, Any]) -> GeoPoint:
        return GeoPoint(lat=float(value["lat"]), lng=float(value["lng"]))

    def _line_distance_meters(self, points: list[dict[str, Any]], mode: str) -> int:
        if len(points) < 2:
            return 0
        distance = 0
        for origin, destination in zip(points, points[1:]):
            distance += self._mode_distance_meters(self._point(origin), self._point(destination), mode)
        return distance

    def _mode_distance_meters(self, origin: GeoPoint, destination: GeoPoint, mode: str) -> int:
        distance_km = self._distance_km(origin, destination)
        settings = self.defaults.get(mode, self.defaults["walk"])
        return max(1, round(distance_km * float(settings.get("detour_factor", 1.0)) * 1000))

    def _mode_minutes(self, distance_meters: int, mode: str, city: dict[str, Any], departure_time: str | None) -> int:
        settings = self.defaults.get(mode, self.defaults["walk"])
        speed = float(settings.get("speed_kmh", 5))
        base = float(settings.get("base_wait_minutes", 0))
        access = float(settings.get("station_access_minutes", 0)) if mode in {"metro", "bus"} else 0
        min_minutes = int(settings.get("min_minutes", 1))
        moving = (distance_meters / 1000) / speed * 60
        multiplier = self._peak_multiplier(city, mode, departure_time)
        return max(min_minutes, round((base + access + moving) * multiplier))

    def _peak_multiplier(self, city: dict[str, Any], mode: str, departure_time: str | None) -> float:
        minutes = self._parse_time(departure_time or "14:00")
        key = f"{mode}_multiplier"
        for peak in city.get("peak_hours", []):
            if self._parse_time(peak["start"]) <= minutes <= self._parse_time(peak["end"]):
                return float(peak.get(key, 1.0))
        return 1.0

    def _polyline(self, points: list[GeoPoint]) -> str:
        return ";".join(f"{point.lng:.6f},{point.lat:.6f}" for point in points)

    def _midpoint(self, origin: GeoPoint, destination: GeoPoint, offset: float = 0.0) -> GeoPoint:
        return GeoPoint(lat=(origin.lat + destination.lat) / 2 + offset, lng=(origin.lng + destination.lng) / 2 - offset)

    def _distance_km(self, origin: GeoPoint, destination: GeoPoint) -> float:
        radius_km = 6371
        dlat = math.radians(destination.lat - origin.lat)
        dlng = math.radians(destination.lng - origin.lng)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(origin.lat)) * math.cos(math.radians(destination.lat)) * math.sin(dlng / 2) ** 2
        )
        return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _parse_time(self, value: str) -> int:
        try:
            hour, minute = value.split(":", 1)
            return int(hour) * 60 + int(minute)
        except (AttributeError, ValueError):
            return 14 * 60

    def _normalize_mode(self, mode: str) -> str:
        if "metro" in mode or "地铁" in mode:
            return "metro"
        if "bus" in mode or "公交" in mode:
            return "bus"
        if "taxi" in mode or "drive" in mode or "打车" in mode:
            return "taxi"
        return "walk"

    def _access_instruction(self, distance_meters: int, minutes: int, station_name: str, mode: str) -> str:
        action = "进站" if mode == "metro" else "上车"
        if distance_meters <= 80:
            return f"从附近的{station_name}{action}，步行约 {minutes} 分钟"
        return f"步行约 {self._display_meters(distance_meters)} 米至 {station_name}，约 {minutes} 分钟"

    def _egress_instruction(self, distance_meters: int, minutes: int, mode: str) -> str:
        if distance_meters <= 80:
            return f"{'出站' if mode == 'metro' else '下车'}后到达目的地，步行约 {minutes} 分钟"
        return f"{'出站后' if mode == 'metro' else '下车后'}步行约 {self._display_meters(distance_meters)} 米到达目的地，约 {minutes} 分钟"

    def _transit_instruction(self, verb: str, line_name: str, stop_count: int, end_name: str, distance_meters: int, minutes: int) -> str:
        if line_name.startswith(verb):
            label = line_name
        else:
            label = f"{verb}{line_name}"
        return f"乘坐{label} {stop_count}站 至 {end_name}，约 {self._display_km(distance_meters)} 公里，预计 {minutes} 分钟"

    def _display_meters(self, distance_meters: int) -> int:
        if distance_meters < 100:
            return max(20, round(distance_meters / 10) * 10)
        if distance_meters < 1000:
            return round(distance_meters / 50) * 50
        return round(distance_meters / 100) * 100

    def _display_km(self, distance_meters: int) -> str:
        return f"{distance_meters / 1000:.1f}"
