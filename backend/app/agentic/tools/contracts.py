from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from app.agentic.protocol import ToolCallInfo, ToolResultInfo
from app.agentic.runtime.settings import get_default_settings
from app.agentic.tools.serialization import (
    result_error_message,
    serialize_error,
    serialize_result,
)
from app.agentic.tools.validation import ToolArgumentsError, coerce_arguments
from app.domain.errors import ApplicationError, UpstreamUnavailableError, is_transient_error, log_internal_error

logger = logging.getLogger(__name__)

# 等待 max_parallel_calls 额度的上限。排队不该吃掉执行预算，但也不能无限等：
# 排不上就明确告诉模型「本次未执行」，好过让它以为工具慢而反复重调。
_MAX_QUEUE_WAIT_SECONDS = 5.0

if TYPE_CHECKING:
    from app.agentic.runtime.context import AgentExecutionContext

_current_tool_context: ContextVar["AgentExecutionContext | None"] = ContextVar(
    "agentic_tool_context", default=None
)


def get_current_tool_context() -> "AgentExecutionContext | None":
    """Return the execution context for the currently running tool call."""
    return _current_tool_context.get()


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
    # Instruction tools (e.g. load_skill) must not satisfy data-evidence gates.
    evidence: bool = True
    # "skill" uses a separate per-run budget instead of the data-tool budget.
    budget: Literal["tool", "skill"] = "tool"

    def __post_init__(self) -> None:
        if self.cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds 不能小于 0")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须大于 0")
        if self.max_parallel_calls is not None and self.max_parallel_calls < 1:
            raise ValueError("max_parallel_calls 必须大于 0")
        if self.max_result_characters < 512:
            raise ValueError("max_result_characters 不能小于 512")


def invalid_arguments_data(error: Exception) -> dict[str, str] | None:
    """把参数校验失败转成可安全发到界面的受控字段。

    这里只允许透出 ``ToolArgumentsError`` 自带的 reason/field/detail——它们由
    ``validate_value`` 填充且只来自 schema。JSONDecodeError 不透出任何原文，
    因为它的 message 里含模型自己输出的片段。
    """
    if not isinstance(error, ToolArgumentsError):
        return {"reason": "invalid_json"} if isinstance(error, json.JSONDecodeError) else None
    payload = {"reason": error.reason} if error.reason else {}
    if error.field:
        payload["field"] = error.field
    if error.detail:
        payload["detail"] = error.detail
    return payload or None


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
        *,
        arguments: Any | None = None,
    ) -> ToolResultInfo:
        if self.executor is None:
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=serialize_error("tool_unavailable", f"工具 '{self.name}' 暂不可用"),
                is_error=True,
            )
        executor = self.executor
        # 整体 deadline 已耗尽时直接短路。不短路的话 bounded_timeout 会返回 ~1ms，
        # 每次调用都立刻失败，而 LLM 看到的是「可重试的工具错误」会继续调用，
        # 白白烧掉每轮/总工具配额和一次 LLM 往返。
        if execution_context is not None and execution_context.deadline_exceeded():
            return ToolResultInfo(
                tool_call_id=call.id,
                name=self.name,
                content=serialize_error(
                    "deadline_exceeded", "本次会话时间预算已耗尽，请让 Agent 尽快收敛并作答"
                ),
                is_error=True,
            )
        try:
            if arguments is None:
                arguments = coerce_arguments(json.loads(call.function.arguments), self.parameters)
            settings = execution_context.settings if execution_context is not None else get_default_settings()
            requested_timeout = self.policy.timeout_seconds or settings.chat_tool_timeout_seconds
            timeout_seconds = max(1.0, float(requested_timeout))
            if execution_context is not None:
                timeout_seconds = execution_context.bounded_timeout(timeout_seconds)

            async def invoke():
                token = _current_tool_context.set(execution_context)
                try:
                    return await executor(**arguments)
                finally:
                    _current_tool_context.reset(token)

            if self._semaphore is None:
                async with asyncio.timeout(timeout_seconds):
                    result = await invoke()
            else:
                # 排队时间不计入工具超时。max_parallel_calls 是进程级共享的（工具注册
                # 在 lifespan 里做一次），一个慢请求就能让后来者把整份预算耗在等待上：
                # 一次都没执行却被判「执行超时 + 可重试」，模型原样再调一次、又排一次队。
                queue_timeout = max(1.0, min(_MAX_QUEUE_WAIT_SECONDS, timeout_seconds / 4))
                if execution_context is not None:
                    queue_timeout = execution_context.bounded_timeout(queue_timeout)
                try:
                    await asyncio.wait_for(
                        self._semaphore.acquire(), timeout=queue_timeout
                    )
                except TimeoutError:
                    logger.warning(
                        "Chat 工具 %s 等待并发额度超时: queue_timeout=%.1f",
                        self.name,
                        queue_timeout,
                    )
                    return ToolResultInfo(
                        tool_call_id=call.id,
                        name=call.function.name,
                        content=serialize_error(
                            "tool_queue_timeout",
                            f"工具 {self.name} 等待并发额度超时（{queue_timeout:.0f}秒），本次未执行；"
                            "请先处理已返回的结果，或改用其他工具，不要立刻重复调用",
                            retryable=False,
                        ),
                        is_error=True,
                    )
                try:
                    async with asyncio.timeout(timeout_seconds):
                        result = await invoke()
                finally:
                    self._semaphore.release()
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
            diagnostics = invalid_arguments_data(error)
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=serialize_error(
                    "invalid_arguments",
                    f"工具参数无效：{error}",
                    # 诊断必须有自己的命名空间：payload["data"] 同时也承载工具自报的
                    # 原始返回（见 serialize_result），靠「reason 是否命中枚举」猜来源
                    # 的话，工具多带一个 reason 字段就会显示成一次没发生过的校验诊断。
                    data={"argument_error": diagnostics} if diagnostics else None,
                ),
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
            # 只有瞬时性异常才告诉模型可以原样重试；编程错误/权限错误/配置错误标成
            # 可重试会诱导它拿着同样参数一直调到 max_rounds 耗尽。
            retryable = is_transient_error(error)
            if not retryable:
                detail = f"{detail}；该错误不会因原样重试而消失，请改用其他工具或调整参数"
            return ToolResultInfo(
                tool_call_id=call.id,
                name=call.function.name,
                content=serialize_error("execution_failed", detail, retryable=retryable),
                is_error=True,
            )
