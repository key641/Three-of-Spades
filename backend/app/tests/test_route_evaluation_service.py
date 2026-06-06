import json

import pytest

from app.schemas.intent import Intent
from app.schemas.route import RouteEvaluationRequest, RoutePlanRequest
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_evaluation_service import RouteEvaluationService
from app.services.route_service import RouteService


pytestmark = pytest.mark.anyio


class FailingLLMClient:
    async def complete(self, messages: list[dict], tools: list[dict] | None = None, json_mode: bool = True) -> dict:
        raise RuntimeError("llm unavailable")


class MockLLMClient:
    async def complete(self, messages: list[dict], tools: list[dict] | None = None, json_mode: bool = True) -> dict:
        payload = json.loads(messages[-1]["content"])
        route_id = payload["routes"][0]["route_id"]
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "evaluations": [
                                    {
                                        "route_id": route_id,
                                        "score": 91,
                                        "summary": "节奏均衡，适合首次游玩。",
                                        "highlights": ["点位集中", "预算稳定"],
                                        "risks": ["热门点位可能略拥挤"],
                                        "recommendation": "推荐作为首选方案。",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }


def _evaluation_request() -> RouteEvaluationRequest:
    intent = Intent(city="北京", preferences=["拍照", "咖啡"], duration_hours=6)
    profile = ProfileService().get_profile("user_demo")
    pois = POIService().search(intent, user_profile=profile)
    routes = RouteService().generate_routes(
        RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)
    ).routes
    return RouteEvaluationRequest(intent=intent, user_profile=profile, routes=routes)


async def test_route_evaluation_falls_back_when_llm_fails() -> None:
    request = _evaluation_request()
    response = await RouteEvaluationService(llm_client=FailingLLMClient()).evaluate(request)

    assert len(response.evaluations) == len(request.routes)
    assert all(evaluation.route_id for evaluation in response.evaluations)
    assert all(evaluation.source == "fallback" for evaluation in response.evaluations)
    assert all(0 <= evaluation.score <= 100 for evaluation in response.evaluations)


async def test_route_evaluation_parses_llm_result() -> None:
    request = _evaluation_request()
    response = await RouteEvaluationService(llm_client=MockLLMClient()).evaluate(request)

    assert response.evaluations
    assert response.evaluations[0].route_id == request.routes[0].route_id
    assert response.evaluations[0].score == 91
    assert response.evaluations[0].source == "llm"
