from __future__ import annotations

from app.schemas.intent import Intent
from app.schemas.route import Route


class ResponseComposer:
    def compose_routes(
        self,
        intent: Intent,
        routes: list[Route],
        *,
        degradation_steps: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> str:
        if not routes:
            return self.compose_infeasible(intent, {})
        count = len(routes)
        opening = f"已为你生成 {count} 条可执行路线。"
        if count < 3:
            opening = f"当前条件下找到 {count} 条可执行路线，我先把能走通的方案给你。"
        summaries = [
            f"{index + 1}. {route.title}：{len(route.stops)} 站，约 {route.total_duration_minutes} 分钟，"
            f"人均约 ¥{route.total_cost_per_person}"
            for index, route in enumerate(routes)
        ]
        notes: list[str] = []
        if degradation_steps:
            notes.append("为保证可执行性，已采用轻量路线或降低路线间差异。")
        if warnings:
            notes.extend(warnings[:2])
        return "\n".join([opening, *summaries, *notes])

    def compose_infeasible(self, intent: Intent, diagnostics: dict) -> str:
        dominant = diagnostics.get("dominant_failure") or diagnostics.get("reason")
        explanations = {
            "duration_exceeded": "当前时长不足以容纳这些地点和交通时间",
            "closed_at_arrival": "部分地点在预计到达时间已经停止入场",
            "extreme_budget_exceeded": "当前预算无法覆盖可执行组合",
            "insufficient_combinations": "当前区域可组合的地点不足",
        }
        reason = explanations.get(dominant, "当前条件组合下暂时没有可执行路线")
        return f"{reason}。可以调整区域、出发时间或减少一个站点，我会保留其他条件继续规划。"
