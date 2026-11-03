"""Shared LLM transport: one limiter, bounded retries, deadlines and telemetry."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

import httpx
from openai import APITimeoutError

from app.configuration import get_settings
from app.configuration.schema import Settings
from app.core.metrics import metrics
from app.domain.llm import LLMConfigurationError, llm_error_status_code, looks_like_tools_unsupported
from app.infrastructure.llm import tool_support
from app.infrastructure.llm.adapters import (
    LLMRetryableError,
    extract_usage,
    normalize_retryable_llm_error,
    prepare_completion_kwargs,
    validate_chat_completion_response,
)
from app.infrastructure.llm.capabilities import LLMCapabilities, apply_deployment_limits, capabilities_for_settings
from app.infrastructure.llm.policy import (
    LLMGenerationTimeoutError,
    call_settings,
    generation_scope,
    request_timeout_error,
)


@asynccontextmanager
async def _request_deadline(deadline: float | None):
    scope = asyncio.timeout_at(deadline)
    try:
        async with scope:
            yield
    except TimeoutError as error:
        if not scope.expired():
            raise
        raise LLMGenerationTimeoutError("模型生成总时限已耗尽，请检查模型网关状态或缩小任务范围后重试") from error


@asynccontextmanager
async def _stream_read_guard(deadline: float | None, read_timeout: float):
    """同时受全局 deadline 与单块读超时（read_timeout）双重保护，防止流挂起死等。"""
    now = asyncio.get_running_loop().time()
    effective_deadline = min(deadline, now + read_timeout) if deadline is not None else now + read_timeout
    scope = asyncio.timeout_at(effective_deadline)
    try:
        async with scope:
            yield
    except TimeoutError as error:
        if deadline is not None and now >= deadline:
            raise LLMGenerationTimeoutError("模型生成总时限已耗尽，请检查模型网关状态或缩小任务范围后重试") from error
        raise httpx.ReadTimeout(f"模型流式响应读取超时（超过 {read_timeout:.1f} 秒无响应）") from error


class _AdaptiveConcurrencyLimiter:
    def __init__(self) -> None:
        self._active = 0
        self._condition = asyncio.Condition()

    @asynccontextmanager
    async def slot(self, *, deadline: float | None = None):
        async with _request_deadline(deadline), self._condition:
            await self._condition.wait_for(
                lambda: self._active < max(1, int(get_settings().max_concurrent_llm_requests))
            )
            self._active += 1
        try:
            yield
        finally:
            async with self._condition:
                self._active = max(0, self._active - 1)
                self._condition.notify_all()


logger = logging.getLogger(__name__)
_STREAM_RETRY_BASE_SECONDS = 0.25
_RATE_LIMIT_RETRY_BASE_SECONDS = 2.0


def _compute_retry_delay(normalized: Exception, attempt: int) -> float:
    """计算重试延迟：针对 429 限流使用更大的退避等待（2s, 4s...），其他临时错误沿用 0.25s。"""
    is_rate_limit = llm_error_status_code(normalized) == 429
    base = _RATE_LIMIT_RETRY_BASE_SECONDS if is_rate_limit else _STREAM_RETRY_BASE_SECONDS
    return float(base * (2 ** (attempt - 1)))


_llm_limiter = _AdaptiveConcurrencyLimiter()


def _fallback_settings(settings: Settings, model: str) -> Settings:
    """按备用模型派生设置（只改 model，其余端点/凭证不变）。"""
    derived: Settings = settings.model_copy(update={"llm_model": model})
    return derived


def _pooled_fallback_client(
    settings: Settings, stack: AsyncExitStack,
) -> Callable[[str], Awaitable[Any]]:
    """租一个备用模型的运行时客户端，用完由 ``stack`` 归还连接池。

    直接新建 ``AsyncOpenAI`` 会为每次降级重做 DNS/TCP/TLS 握手，而 429 恰恰是
    成批出现、系统已经吃紧的时候。改用与主路径相同的池（池键含 model），降级
    客户端因此能复用连接，也不会与主客户端抢同一个池条目。
    """

    async def build(model: str) -> Any:
        # 延迟导入避免 completion -> runtime -> ... 的模块级循环依赖。
        from app.infrastructure.llm.runtime import borrow_async_openai_chat_runtime

        runtime = await stack.enter_async_context(
            borrow_async_openai_chat_runtime(_fallback_settings(settings, model))
        )
        return runtime.client

    return build


def _prepare_request(
    client: Any, kwargs: dict[str, Any], *, settings: Settings, max_completion_tokens: int | None,
) -> dict[str, Any]:
    """Keep both explicit budgets until shared shaping computes their minimum."""
    request = dict(kwargs)
    capabilities = getattr(client, "capabilities", None)
    if not isinstance(capabilities, LLMCapabilities):
        capabilities = capabilities_for_settings(settings, model=str(request.get("model", settings.llm_model)))
    capabilities = apply_deployment_limits(capabilities, settings)
    if max_completion_tokens is not None:
        request["max_completion_tokens"] = max_completion_tokens
    if request.get("max_tokens") is None and request.get("max_completion_tokens") is None:
        request["max_tokens"] = settings.chat_max_completion_tokens
    if request.get("stream") and capabilities.stream_include_usage:
        request.setdefault("stream_options", {"include_usage": True})
    prepared: dict[str, Any] = prepare_completion_kwargs(request, capabilities)
    return prepared


def _prepare_fallback_request(
    client: Any,
    request_kwargs: dict[str, Any],
    *,
    settings: Settings,
    max_completion_tokens: int | None,
    metric_stage: str,
) -> dict[str, Any] | None:
    """按备用模型重新整形请求；新模型装不下原请求时返回 ``None`` 放弃降级。

    降级是尽力而为的兜底，**绝不能比不降级更差**。备用模型可能不支持工具调用、
    严格 JSON Schema 等主模型支持的能力，此时 ``prepare_completion_kwargs`` 会抛
    ``LLMConfigurationError``；如果放任它向上抛，用户看到的会是"当前模型网关未启用
    工具调用能力"，而真正的失败原因（429 限流）被完全掩盖。
    """
    try:
        return _prepare_request(
            client, request_kwargs, settings=settings, max_completion_tokens=max_completion_tokens,
        )
    except LLMConfigurationError as config_error:
        logger.warning(
            "备用模型不支持原请求所需的参数，放弃降级并保留原错误: stage=%s reason=%s",
            metric_stage,
            str(config_error),
        )
        metrics.record_provider_attempt(
            "llm_chat",
            operation="fallback_incompatible",
            success=False,
            duration_ms=0.0,
            error_type="LLMConfigurationError",
            fallback=True,
        )
        return None


def _degrade_tools_if_rejected(
    error: BaseException,
    request_kwargs: dict[str, Any],
    *,
    settings: Settings,
    metric_stage: str,
) -> bool:
    """网关明确拒绝 tools 时：记住该路由不支持工具，摘掉工具参数并允许重试一次。

    与 ``normalize_retryable_llm_error`` 的分工：那条负责"这次错误能不能重试"，
    这条只负责"这个路由有没有工具能力"，不改变错误分类，也不会把 401/403/429
    误判成能力缺失（判定在 domain 层统一收口）。
    """
    if not request_kwargs.get("tools"):
        return False
    if not looks_like_tools_unsupported(error):
        return False
    model = str(request_kwargs.get("model", "") or "")
    route = tool_support.route_key_for_settings(settings, model=model)
    tool_support.mark_tools_unsupported(route)
    for key in ("tools", "tool_choice", "parallel_tool_calls"):
        request_kwargs.pop(key, None)
    metrics.record_provider_attempt(
        "llm_chat",
        operation="tools_unsupported",
        success=False,
        duration_ms=0.0,
        error_type="ToolsUnsupported",
    )
    logger.warning(
        "模型网关拒绝工具调用，已按无工具网关重试一次: model=%s provider=%s stage=%s",
        model,
        route.provider,
        metric_stage,
    )
    return True


def _is_quota_or_rate_limit(error: BaseException) -> bool:
    """判定是否为配额/限流类错误（额度耗尽或频率受限）。

    只认「状态码」或「明确的配额/限流措辞」，不再拿裸 ``429`` 做子串匹配：
    上游 400 消息里出现 ``max_tokens 14290 exceeds`` 这类数字很常见，误判会让
    我们自己的参数错误被当成限流而切到备用模型。
    """
    status_code = llm_error_status_code(error)
    if status_code == 429:
        return True
    if status_code is not None:
        # 402（余额不足）同样是账号级额度问题，换模型可能救回来。
        return status_code == 402
    message = str(error).lower()
    return any(
        kw in message
        for kw in (
            "quota exceeded",
            "quota_exceeded",
            "insufficient_quota",
            "insufficient quota",
            "rate limit",
            "rate_limit",
            "too many requests",
            "resource exhausted",
            "resource_exhausted",
            "credits exhausted",
            "balance insufficient",
        )
    )


def _is_fallback_eligible(error: BaseException, *, normalized: Exception) -> bool:
    """该错误是否值得切换到备用模型。

    只有「账号级额度/限流」与「上游瞬时故障」两类：前者换模型可能立刻恢复，
    后者说明主模型路由当前不可用。以下**不**降级，因为换模型只会把问题推迟
    并掩盖真实原因：

    * 400/401/403/404/422：请求本身或凭证/权限/模型名有误，备用模型同样会失败；
    * 超时与取消：备用模型可能更慢，且上层已有总时限预算。
    """
    if _is_quota_or_rate_limit(error):
        return True
    status_code = llm_error_status_code(error)
    if status_code is not None:
        # 5xx 等「上游自己挂了」的错误可以尝试备用模型；其余 4xx 一律不降级。
        return status_code >= 500
    return isinstance(normalized, LLMRetryableError) and not isinstance(normalized, TimeoutError)


async def _apply_fallback_model_if_available(
    error: BaseException,
    request_kwargs: dict[str, Any],
    *,
    settings: Settings,
    metric_stage: str,
    transient_attempt: int,
    fallback_client_factory: Callable[[str], Awaitable[Any]] | None = None,
) -> Any | None:
    """主模型额度/限流耗尽或上游不可用时，返回 ``llm_fallback_model`` 的客户端。

    返回新客户端时，调用方必须换掉后续请求用的 client 并**重新整形请求参数**；
    不需要降级（未配置/不可重试/已在备用模型上）时返回 None。

    为什么必须换客户端而不是只改 ``model`` 字段：SDK 封装层在
    ``prepare_completion_kwargs(..., expected_model=self._model)`` 处校验
    「请求模型 == 客户端模型」，只改 kwargs 会让降级请求必然抛
    ``LLMConfigurationError``；同时能力位（temperature/tools/令牌上限）也是按
    客户端模型派生的，两套策略不一致会再次触发同一类错误。
"""
    fallback_model = (getattr(settings, "llm_fallback_model", "") or "").strip()
    if not fallback_model or fallback_client_factory is None:
        return None
    current_model = str(request_kwargs.get("model", "") or "")

    normalized = normalize_retryable_llm_error(error if isinstance(error, Exception) else Exception(str(error)))
    if not _is_fallback_eligible(error, normalized=normalized):
        return None
    # 额度/限流属于账号级问题，立刻切换；其余瞬时故障等重试预算耗尽再降级。
    if not _is_quota_or_rate_limit(error) and transient_attempt < settings.llm_max_attempts:
        return None

    if current_model == fallback_model:
        # 典型误配：简单任务已切到 llm_sub_model，而 llm_fallback_model 正好填了同一个模型。
        # 不改配置校验（存量部署可能已经这么写），只在真正需要兜底时提示。
        logger.warning(
            "备用模型与当前模型相同(%s)，本次无法降级；请把 LLM_FALLBACK_MODEL 设为另一个模型: stage=%s",
            fallback_model,
            metric_stage,
        )
        return None

    try:
        fallback_client = await fallback_client_factory(fallback_model)
    except Exception as build_error:
        # 备用模型配置非法（例如路由未启用工具能力）不能连累主链路：放弃降级，
        # 让原始错误照常向上抛，降级只是尽力而为的兜底。
        logger.warning(
            "备用模型 %s 无法构建客户端，放弃降级: stage=%s error_type=%s",
            fallback_model,
            metric_stage,
            type(build_error).__name__,
        )
        metrics.record_provider_attempt(
            "llm_chat",
            operation="fallback_unavailable",
            success=False,
            duration_ms=0.0,
            error_type=type(build_error).__name__,
            # 与 fallback_to_model / fallback_incompatible 保持一致：三者都属于
            # “想降级但没降成”，必须计入同一个 fallback 总量，否则监控会漏数。
            fallback=True,
        )
        return None

    logger.warning(
        "上游模型 %s 触发降级 (%s)，自动切换到备用模型 %s: stage=%s",
        current_model,
        "429/额度耗尽" if _is_quota_or_rate_limit(error) else f"上游故障({type(error).__name__})",
        fallback_model,
        metric_stage,
    )
    metrics.record_provider_attempt(
        "llm_chat",
        operation="fallback_to_model",
        success=True,
        duration_ms=0.0,
        fallback=True,
    )
    request_kwargs["model"] = fallback_model
    return fallback_client


async def create_chat_completion(
    client,
    *,
    metric_stage: str = "agentic.completion@v1",
    max_completion_tokens: int | None = None,
    request_timeout: float | None = None,
    **kwargs,
) -> Any:
    """在全局排队槽位中执行一次非流式 Chat Completion。"""
    settings = call_settings()
    request_kwargs = _prepare_request(client, kwargs, settings=settings, max_completion_tokens=max_completion_tokens)
    scope_timeout = (
        min(float(request_timeout), float(settings.llm_generation_timeout_seconds))
        if request_timeout is not None
        else float(settings.llm_generation_timeout_seconds)
    )
    if request_timeout is not None:
        request_kwargs["timeout"] = float(request_timeout)
    started_at = time.perf_counter()
    queue_wait_ms = 0.0
    # 降级租到的运行时统一由 exit stack 归还连接池：成功/异常/取消都不会泄漏。
    async with AsyncExitStack() as fallback_stack:
        try:
            async with generation_scope(settings, timeout_seconds=scope_timeout), _llm_limiter.slot():
                queue_wait_ms = (time.perf_counter() - started_at) * 1000
                # 工具降级重试与瞬时故障重试分开计数：前者每个调用最多一次，
                # 不能吃掉 llm_max_attempts 里给 429/5xx 准备的预算。
                transient_attempt = 0
                tool_retry_used = False
                fallback_attempted = False
                while True:
                    transient_attempt += 1
                    try:
                        response = await client.chat.completions.create(**request_kwargs)
                        validate_chat_completion_response(response)
                        break
                    except Exception as error:
                        if not tool_retry_used and _degrade_tools_if_rejected(
                            error, request_kwargs, settings=settings, metric_stage=metric_stage,
                        ):
                            tool_retry_used = True
                            continue
                        if not fallback_attempted:
                            new_client = await _apply_fallback_model_if_available(
                                error, request_kwargs, settings=settings, metric_stage=metric_stage,
                                transient_attempt=transient_attempt,
                                fallback_client_factory=_pooled_fallback_client(settings, fallback_stack),
                            )
                            if new_client is not None:
                                # 客户端已租到，降级机会就此用完：即使整形失败也不再重试降级。
                                fallback_attempted = True
                                # 客户端换了，能力位与请求整形必须按新模型重算。
                                # 整形可能因备用模型缺能力而失败，此时放弃降级、保留原错误。
                                reshaped = _prepare_fallback_request(
                                    new_client, request_kwargs, settings=settings,
                                    max_completion_tokens=max_completion_tokens,
                                    metric_stage=metric_stage,
                                )
                                if reshaped is not None:
                                    client = new_client
                                    request_kwargs = reshaped
                                    if request_timeout is not None:
                                        request_kwargs["timeout"] = float(request_timeout)
                                    transient_attempt = 0
                                    tool_retry_used = False
                                    continue
                        normalized = normalize_retryable_llm_error(error)
                        if (
                            not isinstance(normalized, LLMRetryableError)
                            or transient_attempt >= settings.llm_max_attempts
                        ):
                            if normalized is error:
                                raise
                            raise normalized from error
                        await asyncio.sleep(_compute_retry_delay(normalized, transient_attempt))
        except asyncio.CancelledError:
            duration_ms = (time.perf_counter() - started_at) * 1000
            metrics.record_llm_prompt(
                metric_stage,
                str(request_kwargs.get("model", "")),
                success=False,
                duration_ms=duration_ms,
                queue_wait_ms=queue_wait_ms,
                cancelled=True,
                error_type="CancelledError",
            )
            raise
        except Exception as exc:
            duration_ms = (time.perf_counter() - started_at) * 1000
            metrics.record_provider_attempt(
                "llm_chat",
                operation="completion",
                success=False,
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
            )
            metrics.record_llm_prompt(
                metric_stage,
                str(request_kwargs.get("model", "")),
                success=False,
                duration_ms=duration_ms,
                queue_wait_ms=queue_wait_ms,
                error_type=type(exc).__name__,
            )
            raise
    duration_ms = (time.perf_counter() - started_at) * 1000
    usage = extract_usage(response)
    metrics.record_provider_attempt(
        "llm_chat",
        operation="completion",
        success=True,
        duration_ms=duration_ms,
    )
    metrics.record_llm_prompt(
        metric_stage,
        str(request_kwargs.get("model", "")),
        success=True,
        duration_ms=duration_ms,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        queue_wait_ms=queue_wait_ms,
    )
    return response


async def _close_provider_stream(stream: Any) -> None:
    """Close provider response bodies on success, failure, cancellation and generator close."""
    close = getattr(stream, "aclose", None) or getattr(stream, "close", None)
    if not callable(close):
        return
    try:
        async with asyncio.timeout(5):
            result = close()
            if inspect.isawaitable(result):
                await result
    except Exception as exc:
        # 清理失败不能覆盖原始请求异常，也不能触发已完成请求的重试。
        logger.warning("LLM stream cleanup failed: error_type=%s", type(exc).__name__)


async def stream_chat_completion(
    client,
    *,
    metric_stage: str = "agentic.stream@v1",
    max_completion_tokens: int | None = None,
    request_timeout: float | None = None,
    **kwargs,
) -> AsyncGenerator[Any, None]:
    """Hold one LLM slot for the stream and retry transient failures before the first chunk."""
    settings = call_settings()
    request_kwargs = _prepare_request(client, kwargs, settings=settings, max_completion_tokens=max_completion_tokens)
    effective_timeout = (
        min(float(request_timeout), float(settings.llm_generation_timeout_seconds))
        if request_timeout is not None
        else float(settings.llm_generation_timeout_seconds)
    )
    if request_timeout is not None:
        request_kwargs["timeout"] = float(request_timeout)
    started_at = time.perf_counter()
    usage = None
    ttft_ms = None
    yielded_chunk = False
    deadline = asyncio.get_running_loop().time() + effective_timeout
    # 降级租到的运行时统一由 exit stack 归还连接池。
    async with AsyncExitStack() as fallback_stack:
        async with _llm_limiter.slot(deadline=deadline):
            queue_wait_ms = (time.perf_counter() - started_at) * 1000
            # 与 create_chat_completion 一致：工具降级重试独立于瞬时故障重试预算。
            transient_attempt = 0
            tool_retry_used = False
            fallback_attempted = False
            while True:
                transient_attempt += 1
                read_timeout = float(request_timeout) if request_timeout is not None else float(settings.llm_timeout_seconds)
                try:
                    async with _stream_read_guard(deadline, read_timeout):
                        stream = await client.chat.completions.create(**request_kwargs)
                    try:
                        iterator = aiter(stream)
                        while True:
                            try:
                                async with _stream_read_guard(deadline, read_timeout):
                                    chunk = await anext(iterator)
                            except StopAsyncIteration:
                                break
                            yielded_chunk = True
                            if ttft_ms is None:
                                ttft_ms = (time.perf_counter() - started_at) * 1000
                            usage = extract_usage(chunk) or usage
                            yield chunk
                    finally:
                        await _close_provider_stream(stream)
                    break
                except asyncio.CancelledError:
                    duration_ms = (time.perf_counter() - started_at) * 1000
                    metrics.record_llm_prompt(
                        metric_stage,
                        str(request_kwargs.get("model", "")),
                        success=False,
                        duration_ms=duration_ms,
                        queue_wait_ms=queue_wait_ms,
                        ttft_ms=ttft_ms,
                        cancelled=True,
                        error_type="CancelledError",
                    )
                    raise
                except Exception as exc:
                    if (
                        not tool_retry_used
                        and not yielded_chunk
                        and _degrade_tools_if_rejected(
                            exc, request_kwargs, settings=settings, metric_stage=metric_stage,
                        )
                    ):
                        # 首块之前才允许重放：已经吐过内容再重试会重复计费/重复输出。
                        tool_retry_used = True
                        continue
                    if (
                        not fallback_attempted
                        and not yielded_chunk
                    ):
                        new_client = await _apply_fallback_model_if_available(
                            exc, request_kwargs, settings=settings, metric_stage=metric_stage,
                            transient_attempt=transient_attempt,
                            fallback_client_factory=_pooled_fallback_client(settings, fallback_stack),
                        )
                        if new_client is not None:
                            # 客户端已租到，降级机会就此用完：即使整形失败也不再重试降级。
                            fallback_attempted = True
                            # 客户端换了，能力位与请求整形必须按新模型重算。
                            # 整形可能因备用模型缺能力而失败，此时放弃降级、保留原错误。
                            reshaped = _prepare_fallback_request(
                                new_client, request_kwargs, settings=settings,
                                max_completion_tokens=max_completion_tokens,
                                metric_stage=metric_stage,
                            )
                            if reshaped is not None:
                                client = new_client
                                request_kwargs = reshaped
                                if request_timeout is not None:
                                    request_kwargs["timeout"] = float(request_timeout)
                                transient_attempt = 0
                                tool_retry_used = False
                                continue
                    normalized = (
                        request_timeout_error(
                            exc, settings=settings, elapsed_seconds=time.perf_counter() - started_at,
                        )
                        if isinstance(exc, (TimeoutError, APITimeoutError, httpx.TimeoutException))
                        and not isinstance(exc, LLMGenerationTimeoutError)
                        else normalize_retryable_llm_error(exc)
                    )
                    can_retry = (
                        isinstance(normalized, LLMRetryableError)
                        and not yielded_chunk
                        and transient_attempt < settings.llm_max_attempts
                    )
                    if can_retry:
                        delay = _compute_retry_delay(normalized, transient_attempt)
                        metrics.record_provider_attempt(
                            "llm_chat",
                            operation="stream",
                            success=False,
                            duration_ms=(time.perf_counter() - started_at) * 1000,
                            error_type=type(normalized).__name__,
                        )
                        logger.info(
                            "LLM流式上游临时失败，准备重试: model=%s attempt=%s/%s delay=%.2fs error_type=%s",
                            request_kwargs.get("model", ""),
                            transient_attempt,
                            settings.llm_max_attempts,
                            delay,
                            type(normalized).__name__,
                        )
                        async with _request_deadline(deadline):
                            await asyncio.sleep(delay)
                        continue

                    duration_ms = (time.perf_counter() - started_at) * 1000
                    metrics.record_provider_attempt(
                        "llm_chat",
                        operation="stream",
                        success=False,
                        duration_ms=duration_ms,
                        error_type=type(normalized).__name__,
                    )
                    metrics.record_llm_prompt(
                        metric_stage,
                        str(request_kwargs.get("model", "")),
                        success=False,
                        duration_ms=duration_ms,
                        queue_wait_ms=queue_wait_ms,
                        ttft_ms=ttft_ms,
                        error_type=type(normalized).__name__,
                    )
                    if normalized is exc:
                        raise
                    raise normalized from exc

    duration_ms = (time.perf_counter() - started_at) * 1000
    metrics.record_provider_attempt(
        "llm_chat",
        operation="stream",
        success=True,
        duration_ms=duration_ms,
    )
    metrics.record_llm_prompt(
        metric_stage,
        str(request_kwargs.get("model", "")),
        success=True,
        duration_ms=duration_ms,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        queue_wait_ms=queue_wait_ms,
        ttft_ms=ttft_ms,
    )
