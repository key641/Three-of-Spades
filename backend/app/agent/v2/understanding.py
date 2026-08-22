from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.agent.intent_enhancer import (
    enhance_intent_from_message,
    extract_explicit_trip_fields,
    extract_removed_preferences,
)
from app.agent.v2.models import (
    ConstraintSource,
    LocationRef,
    StatePatch,
    TripStateV2,
    TurnUnderstanding,
)
from app.agent.v2.contextual_needs import ContextualNeedEngine
from app.agent.v2.temporal import normalize_clock_time
from app.schemas.chat import ChatRequest
from app.schemas.intent import Intent


logger = logging.getLogger("app.agent.v2.understanding")


SYSTEM_PROMPT = """你是出行规划系统的单轮理解器。只输出 JSON，不生成路线或回复。
输出字段：turn_type、state_patch、route_id、stop_id、scope、ambiguities、confidence。
ambiguities 每项使用 {field, kind, description, candidate_values}；kind 只能是 missing/conflict/vague/unsupported。
turn_type 只能是 new_plan/add/modify/remove/route_question/replan/select/chat。
state_patch 每项包含 op(add/replace/remove)、path、value、source(user_explicit/inferred)、confidence、evidence。
只提取用户本轮明确表达或明确修改的字段，不补系统默认值，不输出隐藏推理。
用餐时间需求由系统根据标准化时间窗确定，不要根据时间主动写 implicit_needs。
用户明确要求正餐时写 must_include add "meal"；用户明确表示不吃饭、不安排餐饮、已经吃过
或跳过午/晚饭时，从 must_include 和 implicit_needs remove "meal"。不要把咖啡或下午茶当作正餐。
字段路径仅限：city、people_count、start_location、start_time、duration_minutes、budget_per_person、
target_district、target_business_area、scenario、preferences、avoidances、must_include、implicit_needs。"""


class TurnUnderstandingService:
    def __init__(self, llm_client=None) -> None:
        self.llm_client = llm_client
        self.contextual_needs = ContextualNeedEngine()

    async def understand(
        self,
        request: ChatRequest,
        state: TripStateV2,
        *,
        allow_llm: bool = True,
    ) -> TurnUnderstanding:
        if allow_llm and self.llm_client is not None:
            parsed = await self._understand_with_llm(request, state)
            if parsed is not None:
                return self._merge_request_context(parsed, request, state)
        return self._fallback(request, state)

    async def _understand_with_llm(self, request: ChatRequest, state: TripStateV2) -> TurnUnderstanding | None:
        payload = {
            "message": request.message,
            "has_state": state.state_version > 0,
            "state_summary": {
                "city": state.scalar_value("city"),
                "people_count": state.scalar_value("people_count"),
                "start_location": state.scalar_value("start_location"),
                "start_time": state.scalar_value("start_time", "14:00"),
                "duration_minutes": state.scalar_value("duration_minutes", 360),
                "budget_per_person": state.scalar_value("budget_per_person"),
                "preferences": [item.value for item in state.preferences],
                "implicit_needs": [item.value for item in state.implicit_needs],
                "active_route_id": state.active_route_id,
            },
        }
        try:
            response = await self.llm_client.complete(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
                ],
                json_mode=True,
            )
            content = response["choices"][0]["message"]["content"]
            data = self._json_object(content)
            data["mode"] = "llm"
            return TurnUnderstanding.model_validate(data)
        except Exception as exc:
            logger.warning("v2 understanding fallback error=%s", type(exc).__name__)
            return None

    def _fallback(self, request: ChatRequest, state: TripStateV2) -> TurnUnderstanding:
        message = request.message.strip()
        explicit = extract_explicit_trip_fields(message)
        enhanced = enhance_intent_from_message(Intent(city=""), message)
        patches: list[StatePatch] = []
        evidence = message[:120]
        field_map = {
            "city": "city",
            "people_count": "people_count",
            "start_time": "start_time",
            "budget_per_person": "budget_per_person",
            "target_district": "target_district",
            "target_business_area": "target_business_area",
        }
        for source_field, target_field in field_map.items():
            if source_field in explicit:
                if target_field in {"target_district", "target_business_area"} and str(explicit[source_field]) in set(enhanced.preferences):
                    continue
                patches.append(self._patch(target_field, explicit[source_field], evidence))
        if "duration_hours" in explicit:
            patches.append(self._patch("duration_minutes", int(explicit["duration_hours"]) * 60, evidence))
        if explicit.get("start_location_name"):
            patches.append(
                self._patch(
                    "start_location",
                    LocationRef(
                        name=str(explicit["start_location_name"]),
                        city=str(explicit.get("city") or state.scalar_value("city") or "") or None,
                        precision="exact",
                    ).model_dump(),
                    evidence,
                )
            )

        existing_preferences = {str(item.value) for item in state.preferences}
        added_preferences = [value for value in enhanced.preferences if value not in existing_preferences]
        if added_preferences:
            patches.append(self._patch("preferences", added_preferences, evidence, op="add"))
        if enhanced.avoid_tags:
            patches.append(self._patch("avoidances", enhanced.avoid_tags, evidence, op="add"))
        removed = extract_removed_preferences(message)
        if removed:
            patches.append(self._patch("preferences", removed, evidence, op="remove"))

        patches.extend(self._meal_context_patches(request, state, patches))

        if not any(patch.path == "/city" for patch in patches) and request.city and state.city is None:
            patches.append(
                StatePatch(
                    op="replace",
                    path="/city",
                    value=request.city,
                    source=ConstraintSource.PROFILE,
                    confidence=0.9,
                    evidence="request.city",
                )
            )
        has_explicit_start = any(patch.path == "/start_location" for patch in patches)
        if not has_explicit_start and state.start_location is None and request.start_lat is not None and request.start_lng is not None:
            patches.append(
                StatePatch(
                    op="replace",
                    path="/start_location",
                    value=LocationRef(
                        name=request.start_location_name or "当前位置",
                        lat=request.start_lat,
                        lng=request.start_lng,
                        city=request.city,
                        precision="gps",
                    ).model_dump(),
                    source=ConstraintSource.GPS,
                    confidence=0.95,
                    evidence="request GPS",
                )
            )

        return TurnUnderstanding(
            turn_type=self._turn_type(message, state, bool(removed)),
            state_patch=patches,
            confidence=0.78 if patches else 0.45,
            mode="fallback",
        )

    def _merge_request_context(
        self, understanding: TurnUnderstanding, request: ChatRequest, state: TripStateV2
    ) -> TurnUnderstanding:
        model_patches = [
            patch for patch in understanding.state_patch
            if not (
                patch.path.strip("/") == "implicit_needs"
                and patch.source == ConstraintSource.INFERRED
                and "meal" in (patch.value if isinstance(patch.value, list) else [patch.value])
            )
        ]
        paths = {patch.path.strip("/") for patch in model_patches}
        extra: list[StatePatch] = []
        if "city" not in paths and request.city and state.city is None:
            extra.append(
                StatePatch(
                    op="replace", path="/city", value=request.city,
                    source=ConstraintSource.PROFILE, confidence=0.9, evidence="request.city",
                )
            )
        if (
            "start_location" not in paths
            and state.start_location is None
            and request.start_lat is not None
            and request.start_lng is not None
        ):
            extra.append(
                StatePatch(
                    op="replace",
                    path="/start_location",
                    value=LocationRef(
                        name=request.start_location_name or "当前位置",
                        lat=request.start_lat,
                        lng=request.start_lng,
                        city=request.city,
                        precision="gps",
                    ).model_dump(),
                    source=ConstraintSource.GPS,
                    confidence=0.95,
                    evidence="request GPS",
                )
            )
        explicit_preferences = enhance_intent_from_message(Intent(city=""), request.message).preferences
        removed_preferences = {
            str(value)
            for patch in model_patches
            if patch.path.strip("/") == "preferences" and patch.op == "remove"
            for value in (patch.value if isinstance(patch.value, list) else [patch.value])
        }
        model_preferences = {
            str(value)
            for patch in model_patches
            if patch.path.strip("/") == "preferences" and patch.op != "remove"
            for value in (patch.value if isinstance(patch.value, list) else [patch.value])
        }
        validated_preferences = [
            value for value in explicit_preferences
            if value not in model_preferences and value not in removed_preferences
        ]
        if validated_preferences:
            extra.append(StatePatch(
                op="add",
                path="/preferences",
                value=validated_preferences,
                source=ConstraintSource.USER_EXPLICIT,
                confidence=0.98,
                evidence=request.message[:120],
            ))
        extra.extend(self._meal_context_patches(request, state, [*model_patches, *extra]))
        normalized_patches = [*model_patches, *extra]
        changed = normalized_patches != understanding.state_patch
        return understanding.model_copy(update={
            "state_patch": normalized_patches,
            "mode": "hybrid" if changed else understanding.mode,
        })

    def _meal_context_patches(
        self,
        request: ChatRequest,
        state: TripStateV2,
        patches: list[StatePatch],
    ) -> list[StatePatch]:
        message = request.message.strip()
        existing_meal = any(str(item.value) == "meal" for item in state.implicit_needs)
        negative = bool(re.search(r"(不吃饭|不用吃饭|不安排(?:吃饭|餐饮|正餐)|不要(?:吃饭|餐饮|正餐)|已经吃过|吃过了|跳过(?:午饭|午餐|晚饭|晚餐))", message))
        meal_patch_present = any(
            patch.path.strip("/") == "implicit_needs"
            and "meal" in (patch.value if isinstance(patch.value, list) else [patch.value])
            for patch in patches
        )
        if negative:
            if existing_meal or meal_patch_present:
                return [StatePatch(
                    op="remove",
                    path="/implicit_needs",
                    value=["meal"],
                    source=ConstraintSource.USER_EXPLICIT,
                    confidence=1.0,
                    evidence=message[:120],
                )]
            return []
        if existing_meal or meal_patch_present:
            return []

        start_time = self._projected_patch_value(patches, "start_time", state.scalar_value("start_time", "14:00"))
        duration = self._projected_patch_value(patches, "duration_minutes", state.scalar_value("duration_minutes", 360))
        try:
            normalized_start = normalize_clock_time(start_time)
            if normalized_start is None:
                return []
            hour, minute = normalized_start.split(":", 1)
            start_minutes = int(hour) * 60 + int(minute)
            duration_minutes = max(0, int(duration))
        except (TypeError, ValueError):
            return []
        end_minutes = start_minutes + duration_minutes
        covered = self.contextual_needs.required_meal_windows(start_minutes, duration_minutes)
        if not covered:
            return []
        return [StatePatch(
            op="add",
            path="/implicit_needs",
            value=["meal"],
            source=ConstraintSource.INFERRED,
            confidence=0.9,
            evidence=f"行程时间窗覆盖{'、'.join(covered)}时段",
        )]

    @staticmethod
    def _projected_patch_value(patches: list[StatePatch], field: str, default: Any) -> Any:
        for patch in reversed(patches):
            if patch.path.strip("/") == field and patch.op != "remove":
                return patch.value
        return default

    def _patch(self, field: str, value: Any, evidence: str, op: str = "replace") -> StatePatch:
        return StatePatch(
            op=op,
            path=f"/{field}",
            value=value,
            source=ConstraintSource.USER_EXPLICIT,
            confidence=0.98,
            evidence=evidence,
        )

    def _turn_type(self, message: str, state: TripStateV2, has_removal: bool) -> str:
        if has_removal:
            return "remove"
        if re.search(r"(第\s*[一二三四五六七八九十\d]+\s*站|换掉|替换)", message) and state.current_route_ids:
            return "replan"
        if any(term in message for term in ["怎么走", "多远", "多久", "为什么推荐", "几点到"]):
            return "route_question"
        if state.state_version == 0 or any(term in message for term in ["重新规划", "新行程", "重新来"]):
            return "new_plan"
        if any(term in message for term in ["改成", "降到", "提高到", "换成", "其他不变"]):
            return "modify"
        return "add"

    def _json_object(self, content: Any) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        text = str(content).strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S)
        return json.loads(text)
