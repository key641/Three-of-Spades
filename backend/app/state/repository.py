from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import json
import sqlite3
from threading import RLock
from typing import Any

from app.agent.v2.models import StateEvent, TripStateV2


class StateConflictError(RuntimeError):
    pass


class StateRepository(ABC):
    @abstractmethod
    def load(self, session_id: str) -> TripStateV2 | None: ...

    @abstractmethod
    def save(self, state: TripStateV2, event: StateEvent, expected_version: int) -> None: ...

    @abstractmethod
    def get_request_result(self, request_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def save_request_result(self, request_id: str, session_id: str, payload: dict[str, Any]) -> None: ...


class InMemoryStateRepository(StateRepository):
    def __init__(self) -> None:
        self._states: dict[str, TripStateV2] = {}
        self._events: list[StateEvent] = []
        self._results: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def load(self, session_id: str) -> TripStateV2 | None:
        with self._lock:
            state = self._states.get(session_id)
            return state.model_copy(deep=True) if state else None

    def save(self, state: TripStateV2, event: StateEvent, expected_version: int) -> None:
        with self._lock:
            current = self._states.get(state.session_id)
            actual = current.state_version if current else 0
            if actual != expected_version:
                raise StateConflictError(f"expected state version {expected_version}, got {actual}")
            self._states[state.session_id] = state.model_copy(deep=True)
            self._events.append(event.model_copy(deep=True))

    def get_request_result(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            payload = self._results.get(request_id)
            return deepcopy_json(payload) if payload else None

    def save_request_result(self, request_id: str, session_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._results.setdefault(request_id, deepcopy_json(payload))


class SQLiteStateRepository(StateRepository):
    def __init__(self, database_path: str | Path) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_session_state (
                    session_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    state_version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS agent_state_events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    base_version INTEGER NOT NULL,
                    new_version INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_agent_events_session
                    ON agent_state_events(session_id, new_version);
                CREATE TABLE IF NOT EXISTS agent_request_results (
                    request_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def load(self, session_id: str) -> TripStateV2 | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM agent_session_state WHERE session_id = ?", (session_id,)
            ).fetchone()
            return TripStateV2.model_validate_json(row["payload"]) if row else None

    def save(self, state: TripStateV2, event: StateEvent, expected_version: int) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state_version FROM agent_session_state WHERE session_id = ?", (state.session_id,)
            ).fetchone()
            actual = int(row["state_version"]) if row else 0
            if actual != expected_version:
                connection.rollback()
                raise StateConflictError(f"expected state version {expected_version}, got {actual}")
            connection.execute(
                """
                INSERT INTO agent_session_state(session_id, schema_version, state_version, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    schema_version=excluded.schema_version,
                    state_version=excluded.state_version,
                    payload=excluded.payload,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (state.session_id, state.schema_version, state.state_version, state.model_dump_json()),
            )
            connection.execute(
                """
                INSERT INTO agent_state_events(
                    event_id, session_id, turn_id, base_version, new_version, event_type, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.session_id,
                    event.turn_id,
                    event.base_version,
                    event.new_version,
                    event.event_type,
                    event.model_dump_json(),
                    event.created_at,
                ),
            )
            connection.commit()

    def get_request_result(self, request_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM agent_request_results WHERE request_id = ?", (request_id,)
            ).fetchone()
            return json.loads(row["payload"]) if row else None

    def save_request_result(self, request_id: str, session_id: str, payload: dict[str, Any]) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO agent_request_results(request_id, session_id, payload) VALUES (?, ?, ?)",
                (request_id, session_id, json.dumps(payload, ensure_ascii=False)),
            )


def deepcopy_json(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    return json.loads(json.dumps(payload, ensure_ascii=False)) if payload is not None else None
