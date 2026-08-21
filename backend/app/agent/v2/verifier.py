from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.route import Route
from app.schemas.user import UserProfile
from app.services.constraint_evaluator import ConstraintEvaluator


class VerificationIssue(BaseModel):
    code: str
    message: str
    route_id: str
    hard: bool = True


class VerificationReport(BaseModel):
    valid_routes: list[Route] = Field(default_factory=list)
    rejected_route_ids: list[str] = Field(default_factory=list)
    issues: list[VerificationIssue] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.valid_routes) and not any(issue.hard for issue in self.issues if issue.route_id in {r.route_id for r in self.valid_routes})


class OutcomeVerifier:
    def __init__(self) -> None:
        self.constraints = ConstraintEvaluator()

    def verify(
        self,
        routes: list[Route],
        intent: Intent,
        profile: UserProfile,
        pois: list[POI],
    ) -> VerificationReport:
        report = VerificationReport()
        poi_by_id = {poi.id: poi for poi in pois}
        from app.schemas.route import RoutePlanRequest

        request = RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)
        for route in routes:
            issues = self._verify_route(route, request, poi_by_id)
            report.issues.extend(issues)
            if any(issue.hard for issue in issues):
                report.rejected_route_ids.append(route.route_id)
            else:
                report.valid_routes.append(route)
        return report

    def _verify_route(self, route: Route, request, poi_by_id: dict[str, POI]) -> list[VerificationIssue]:
        issues: list[VerificationIssue] = []
        ids = [stop.poi_id for stop in route.stops]
        if not ids:
            issues.append(self._issue("empty_route", "路线没有站点", route))
            return issues
        if len(ids) != len(set(ids)):
            issues.append(self._issue("duplicate_stop", "路线包含重复站点", route))
        missing = [poi_id for poi_id in ids if poi_id not in poi_by_id]
        if missing:
            issues.append(self._issue("unknown_poi", "路线包含未知地点", route))
        if any(stop.lat is None or stop.lng is None for stop in route.stops):
            issues.append(self._issue("missing_coordinates", "路线站点缺少坐标", route))
        if not self._times_monotonic(route):
            issues.append(self._issue("invalid_time_order", "路线时间顺序不正确", route))
        constraints = self.constraints.evaluate_route(route, request, poi_by_id)
        for violation in constraints.hard_violations:
            issues.append(self._issue(violation, f"路线违反硬约束：{violation}", route))
        for index, stop in enumerate(route.stops):
            if index > 0 and (
                not stop.transport_mode_from_previous
                or stop.travel_minutes_from_previous is None
                or stop.distance_km_from_previous is None
            ):
                issues.append(self._issue("incomplete_transport", "站点之间缺少交通信息", route))
        return issues

    def _times_monotonic(self, route: Route) -> bool:
        previous = None
        day_offset = 0
        for stop in route.stops:
            start = self._minutes(stop.start_time) + day_offset
            if previous is not None and start < previous:
                if previous - start > 12 * 60:
                    day_offset += 24 * 60
                    start += 24 * 60
                else:
                    return False
            end = self._minutes(stop.end_time) + day_offset
            if end < start:
                end += 24 * 60
                day_offset += 24 * 60
            if end < start:
                return False
            previous = end
        return True

    def _minutes(self, value: str) -> int:
        try:
            hour, minute = value.split(":", 1)
            return int(hour) * 60 + int(minute)
        except (AttributeError, TypeError, ValueError):
            return -1

    def _issue(self, code: str, message: str, route: Route) -> VerificationIssue:
        return VerificationIssue(code=code, message=message, route_id=route.route_id)
