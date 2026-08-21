from app.agent.v2.models import (
    ConstraintSource,
    LocationRef,
    StatePatch,
    TripStateV2,
    TurnUnderstanding,
)
from app.agent.v2.reducer import reduce_state
from app.state.repository import InMemoryStateRepository, SQLiteStateRepository, StateConflictError


def test_explicit_start_is_not_overwritten_by_gps() -> None:
    state = TripStateV2(session_id="s1")
    explicit = TurnUnderstanding(
        turn_type="new_plan",
        state_patch=[
            StatePatch(
                op="replace",
                path="/start_location",
                value=LocationRef(name="国贸", city="北京", precision="exact").model_dump(),
                source=ConstraintSource.USER_EXPLICIT,
            )
        ],
    )
    state, _, _ = reduce_state(state, explicit, "t1")
    gps = TurnUnderstanding(
        turn_type="modify",
        state_patch=[
            StatePatch(
                op="replace",
                path="/start_location",
                value=LocationRef(name="当前位置", lat=39.9, lng=116.4, precision="gps").model_dump(),
                source=ConstraintSource.GPS,
            )
        ],
    )

    updated, _, summary = reduce_state(state, gps, "t2")

    assert updated.start_location.value.name == "国贸"
    assert "start_location" in summary.ignored


def test_reducer_only_changes_fields_in_patch() -> None:
    state = TripStateV2(session_id="s1")
    initial = TurnUnderstanding(
        state_patch=[
            StatePatch(op="replace", path="/city", value="上海"),
            StatePatch(op="replace", path="/people_count", value=5),
            StatePatch(op="replace", path="/budget_per_person", value=400),
        ]
    )
    state, _, _ = reduce_state(state, initial, "t1")
    changed, _, _ = reduce_state(
        state,
        TurnUnderstanding(
            turn_type="modify",
            state_patch=[StatePatch(op="replace", path="/budget_per_person", value=200)],
        ),
        "t2",
    )

    assert changed.scalar_value("city") == "上海"
    assert changed.scalar_value("people_count") == 5
    assert changed.scalar_value("budget_per_person") == 200


def test_sqlite_repository_persists_events_and_is_idempotent(tmp_path) -> None:
    repository = SQLiteStateRepository(tmp_path / "agent.db")
    state = TripStateV2(session_id="s1")
    updated, event, _ = reduce_state(
        state,
        TurnUnderstanding(state_patch=[StatePatch(op="replace", path="/city", value="北京")]),
        "t1",
    )
    repository.save(updated, event, expected_version=0)
    repository.save_request_result("r1", "s1", {"ok": True})
    repository.save_request_result("r1", "s1", {"ok": False})

    restored = repository.load("s1")

    assert restored is not None
    assert restored.state_version == 1
    assert restored.scalar_value("city") == "北京"
    assert repository.get_request_result("r1") == {"ok": True}


def test_repository_rejects_stale_state_version() -> None:
    repository = InMemoryStateRepository()
    base = TripStateV2(session_id="s1")
    first, event, _ = reduce_state(base, TurnUnderstanding(), "t1")
    repository.save(first, event, expected_version=0)

    stale, stale_event, _ = reduce_state(base, TurnUnderstanding(), "t2")
    try:
        repository.save(stale, stale_event, expected_version=0)
    except StateConflictError:
        pass
    else:
        raise AssertionError("stale state write should fail")
