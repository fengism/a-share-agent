from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from app.agentic.protocol import ToolCallInfo, ToolResultInfo
from app.agentic.tools.serialization import (
    result_error_message,
    serialize_error,
    serialize_result,
)
from app.agentic.tools.validation import ToolArgumentsError, validate_value
from app.configuration import get_settings
from app.core.errors import log_internal_error
from app.core.exceptions import ApplicationError, UpstreamUnavailableError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.agentic.runtime.context import AgentExecutionContext


@dataclass(frozen=True)
class ToolPolicy:
    """Cost, cache, freshness, and scope metadata for one tool."""

    cost: Literal["low", "medium", "high"] = "low"
    cache_ttl_seconds: float = 60.0
    freshness: Literal["realtime", "near_realtime", "daily", "static"] = "near_realtime"
    scope: Literal["public", "user"] = "public"
    timeout_seconds: float | None = None
    max_parallel_calls: int | None = None
    max_result_characters: int = 12_000
    # Independent of TTL: pure tools may coalesce within a batch even with TTL=0.
    deduplicate_in_batch: bool = True

    def __post_init__(self) -> None:
        if self.cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds 不能小于 0")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须大于 0")
        if self.max_parallel_calls is not None and self.max_parallel_calls < 1:
            raise ValueError("max_parallel_calls 必须大于 0")
        if self.max_result_characters < 512:
            raise ValueError("max_result_characters 不能小于 512")


class Tool:
    """A registered asynchronous tool with an OpenAI-compatible definition."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
        executor: Callable[..., Awaitable[Any]] | None = None,
        policy: ToolPolicy | None = None,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters or {"type": "object", "properties": {}}
        if self.parameters.get("type") == "object":
            self.parameters.setdefault("additionalProperties", False)
        self.executor = executor
        self.policy = policy or ToolPolicy()
        self._semaphore = (
            asyncio.Semaphore(self.policy.max_parallel_calls)
            if self.policy.max_parallel_calls is not None
            else None
        )

    def to_tool_definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(
        self,
        call: ToolCallInfo,
        execution_context: AgentExecutionContext | None = None,
    ) -> ToolResultInfo:
        if self.executor is None:
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=serialize_error("tool_unavailable", f"工具 '{self.name}' 暂不可用"),
                is_error=True,
            )
        try:
            arguments = json.loads(call.function.arguments)
            validate_value(arguments, self.parameters)
            settings = execution_context.settings if execution_context is not None else get_settings()
            requested_timeout = self.policy.timeout_seconds or settings.chat_tool_timeout_seconds
            timeout_seconds = max(1.0, float(requested_timeout))
            if execution_context is not None:
                timeout_seconds = execution_context.bounded_timeout(timeout_seconds)
            async with asyncio.timeout(timeout_seconds):
                if self._semaphore is None:
                    result = await self.executor(**arguments)
                else:
                    async with self._semaphore:
                        result = await self.executor(**arguments)
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=serialize_result(
                    result,
                    max_result_len=self.policy.max_result_characters,
                ),
                is_error=result_error_message(result) is not None,
            )
        except TimeoutError:
            logger.warning(
                "Chat 工具 %s 执行超时: timeout_seconds=%.1f",
                self.name,
                timeout_seconds,
            )
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=serialize_error(
                    "timeout",
                    f"工具 {self.name} 执行超时，请稍后重试",
                    retryable=True,
                ),
                is_error=True,
            )
        except (json.JSONDecodeError, ToolArgumentsError) as error:
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=serialize_error("invalid_arguments", f"工具参数无效：{error}"),
                is_error=True,
            )
        except ApplicationError as error:
            logger.warning(
                "Chat 工具 %s 返回业务错误 code=%s: %s",
                self.name,
                error.code,
                error.message,
            )
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=serialize_error(
                    error.code,
                    error.message,
                    retryable=isinstance(error, UpstreamUnavailableError),
                ),
                is_error=True,
            )
        except Exception as error:
            _, detail = log_internal_error(
                logger,
                f"Chat 工具 {self.name}",
                error,
                f"工具 {self.name} 执行失败",
            )
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=serialize_error("execution_failed", detail, retryable=True),
                is_error=True,
            )
