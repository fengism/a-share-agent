import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from app.agentic.protocol import ToolCallInfo, ToolResultInfo
from app.agentic.tools.serialization import (
    result_error_message,
    serialize_error,
    serialize_result,
)
from app.agentic.tools.validation import ToolArgumentsError, validate_value
from app.configuration import get_settings
from app.core.errors import log_internal_error

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolPolicy:
    """Cost, cache, freshness, and scope metadata for one tool."""

    cost: Literal["low", "medium", "high"] = "low"
    cache_ttl_seconds: float = 60.0
    freshness: Literal["realtime", "near_realtime", "daily", "static"] = "near_realtime"
    scope: Literal["public", "user"] = "public"

    def __post_init__(self) -> None:
        if self.cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds 不能小于 0")


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

    def to_tool_definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, call: ToolCallInfo) -> ToolResultInfo:
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
            timeout_seconds = max(1, int(get_settings().chat_tool_timeout_seconds))
            async with asyncio.timeout(timeout_seconds):
                result = await self.executor(**arguments)
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=serialize_result(result),
                is_error=result_error_message(result) is not None,
            )
        except (json.JSONDecodeError, ToolArgumentsError) as error:
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=serialize_error("invalid_arguments", f"工具参数无效：{error}"),
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
