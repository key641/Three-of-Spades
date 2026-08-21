from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import inspect
import time
import uuid
from typing import Any

from pydantic import ValidationError

from app.agent.v2.models import ToolResult, ToolSpec, ToolStatus


class AgentTool(ABC):
    spec: ToolSpec

    @abstractmethod
    def run(self, payload: dict[str, Any]) -> ToolResult | Any: ...


class ToolGateway:
    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}
        self._consecutive_failures: dict[str, int] = {}
        self._circuit_open_until: dict[str, float] = {}

    def register(self, tool: AgentTool) -> None:
        if tool.spec.name in self._tools:
            raise ValueError(f"tool already registered: {tool.spec.name}")
        self._tools[tool.spec.name] = tool

    def specs(self) -> list[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]

    def _record_dependency_failure(self, name: str) -> None:
        failures = self._consecutive_failures.get(name, 0) + 1
        self._consecutive_failures[name] = failures
        if failures >= 3:
            self._circuit_open_until[name] = time.monotonic() + 30

    async def execute(self, name: str, payload: dict[str, Any]) -> ToolResult:
        tool = self._tools.get(name)
        call_id = f"call_{uuid.uuid4().hex}"
        if tool is None:
            return ToolResult(
                call_id=call_id,
                tool_name=name,
                status=ToolStatus.INVALID_INPUT,
                error_code="tool_not_found",
                safe_message="请求的能力暂不可用。",
            )
        if self._circuit_open_until.get(name, 0) > time.monotonic():
            return ToolResult(
                call_id=call_id,
                tool_name=name,
                status=ToolStatus.RETRYABLE_ERROR,
                retryable=True,
                error_code="circuit_open",
                safe_message="依赖服务暂时不可用，已停止继续请求。",
                suggested_next_actions=["use_verified_partial_result", "clarify_if_blocking"],
            )
        started = time.perf_counter()
        try:
            if inspect.iscoroutinefunction(tool.run):
                operation = tool.run(payload)
            else:
                operation = asyncio.to_thread(tool.run, payload)
            raw = await asyncio.wait_for(operation, timeout=tool.spec.timeout_ms / 1000)
            result = raw if isinstance(raw, ToolResult) else ToolResult(
                call_id=call_id, tool_name=name, status=ToolStatus.SUCCESS, data=raw
            )
            result.call_id = result.call_id or call_id
            result.duration_ms = round((time.perf_counter() - started) * 1000)
            if result.status in {ToolStatus.SUCCESS, ToolStatus.PARTIAL, ToolStatus.INFEASIBLE}:
                self._consecutive_failures[name] = 0
            elif result.status in {ToolStatus.RETRYABLE_ERROR, ToolStatus.FATAL_ERROR}:
                self._record_dependency_failure(name)
            return result
        except asyncio.TimeoutError:
            self._record_dependency_failure(name)
            return ToolResult(
                call_id=call_id,
                tool_name=name,
                status=ToolStatus.RETRYABLE_ERROR,
                retryable=True,
                duration_ms=round((time.perf_counter() - started) * 1000),
                error_code="timeout",
                safe_message="服务响应超时，请稍后重试。",
            )
        except (ValidationError, TypeError, ValueError) as exc:
            return ToolResult(
                call_id=call_id,
                tool_name=name,
                status=ToolStatus.INVALID_INPUT,
                duration_ms=round((time.perf_counter() - started) * 1000),
                error_code=type(exc).__name__,
                safe_message="输入信息不完整或格式不正确。",
            )
        except Exception as exc:
            self._record_dependency_failure(name)
            return ToolResult(
                call_id=call_id,
                tool_name=name,
                status=ToolStatus.FATAL_ERROR,
                duration_ms=round((time.perf_counter() - started) * 1000),
                error_code=type(exc).__name__,
                safe_message="规划服务暂时不可用，请稍后重试。",
            )
