from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanningExperimentConfig:
    recall_mode: str = "multi"
    fine_rank_mode: str = "objective"
    search_mode: str = "beam"
    diversity_mode: str = "soft"
    route_rerank_enabled: bool = True

    @classmethod
    def baseline(cls) -> "PlanningExperimentConfig":
        return cls(
            recall_mode="legacy",
            fine_rank_mode="balanced",
            search_mode="greedy",
            diversity_mode="zero_overlap",
            route_rerank_enabled=False,
        )
