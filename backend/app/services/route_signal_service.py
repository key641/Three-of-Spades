from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.feedback import FeedbackRequest
from app.schemas.route import Route, RoutePlanRequest


class RouteSignalService:
    """Concurrency-safe append-only route impressions and feedback."""

    def __init__(self, output_path: Path | None = None, db_path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[3]
        self.output_path = output_path
        self.db_path = db_path or root / "data" / "runtime" / "route_signals.db"
        if output_path is None:
            self._initialize()

    def record(self, request: FeedbackRequest) -> None:
        payload = request.model_dump()
        if self.output_path is not None:
            self._append_legacy_jsonl(payload)
            return
        self._insert(
            event_kind="feedback",
            event_type=request.event_type,
            user_id=request.user_id,
            session_id=request.session_id,
            route_id=request.route_id,
            request_id=request.request_id,
            algorithm_version=request.algorithm_version,
            position=None,
            payload=payload,
        )

    def record_impression(
        self,
        request_id: str,
        session_id: str,
        request: RoutePlanRequest,
        routes: list[Route],
        algorithm_version: str = "planning_v2",
    ) -> None:
        if self.output_path is not None:
            return
        for position, route in enumerate(routes, start=1):
            self._insert(
                event_kind="impression",
                event_type="route_impression",
                user_id=request.user_profile.user_id,
                session_id=session_id,
                route_id=route.route_id,
                request_id=request_id,
                algorithm_version=algorithm_version,
                position=position,
                payload={
                    "intent": request.intent.model_dump(),
                    "route": route.model_dump(),
                    "objective": route.objective,
                    "score": route.score,
                    "poi_ids": [stop.poi_id for stop in route.stops],
                },
            )

    def export_jsonl(self, output_path: Path) -> int:
        self._initialize()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with self._connect() as connection, output_path.open("w", encoding="utf-8") as file:
            rows = connection.execute(
                "SELECT event_kind,event_type,user_id,session_id,route_id,request_id,algorithm_version,position,payload_json,created_at FROM route_events ORDER BY id"
            )
            for row in rows:
                payload = {
                    "event_kind": row[0],
                    "event_type": row[1],
                    "user_id": row[2],
                    "session_id": row[3],
                    "route_id": row[4],
                    "request_id": row[5],
                    "algorithm_version": row[6],
                    "position": row[7],
                    "payload": json.loads(row[8]),
                    "recorded_at": row[9],
                }
                file.write(json.dumps(payload, ensure_ascii=False) + "\n")
                count += 1
        return count

    def counts(self) -> dict[str, Any]:
        self._initialize()
        with self._connect() as connection:
            impressions = connection.execute("SELECT COUNT(*) FROM route_events WHERE event_kind='impression'").fetchone()[0]
            selections = connection.execute(
                "SELECT COUNT(*) FROM route_events WHERE event_kind='feedback' AND event_type IN ('route_selected','selected','route_feedback')"
            ).fetchone()[0]
            span = connection.execute(
                "SELECT MIN(created_at),MAX(created_at) FROM route_events WHERE event_kind='impression'"
            ).fetchone()
        return {"impressions": impressions, "selections": selections, "first_at": span[0], "last_at": span[1]}

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS route_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_kind TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    route_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    position INTEGER,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_route_events_request ON route_events(request_id,event_kind)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_route_events_time ON route_events(created_at)")

    def _insert(
        self,
        *,
        event_kind: str,
        event_type: str,
        user_id: str,
        session_id: str,
        route_id: str,
        request_id: str,
        algorithm_version: str,
        position: int | None,
        payload: dict[str, Any],
    ) -> None:
        self._initialize()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO route_events(event_kind,event_type,user_id,session_id,route_id,request_id,algorithm_version,position,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    event_kind,
                    event_type,
                    user_id,
                    session_id,
                    route_id,
                    request_id,
                    algorithm_version,
                    position,
                    json.dumps(payload, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path), timeout=10)

    def _append_legacy_jsonl(self, payload: dict[str, Any]) -> None:
        assert self.output_path is not None
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(payload)
        payload["recorded_at"] = datetime.now(timezone.utc).isoformat()
        with self.output_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")
