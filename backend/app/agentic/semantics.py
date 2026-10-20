"""Shared internal evidence and outcome semantics; independent of business/UI policy.

Acquired data, model-visible data and verified claims are different concepts.
These contracts intentionally make no assertion about claim-level verification.
Retryability is a separate execution decision, not a measure of evidence quality.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.agentic.tools.serialization import has_meaningful_tool_content

ExecutionStatus = Literal["completed", "partial", "failed"]


@dataclass(frozen=True, slots=True)
class EvidenceState:
    acquired: bool
    context_visible: bool | None = None  # None: visibility not tracked by this producer.
    failed: bool = False
    skipped: bool = False

    @property
    def usable_acquisition(self) -> bool:
        return self.acquired and not self.failed

    @property
    def usable_context(self) -> bool:
        # Replayed valid evidence may be skipped=True. A budget rejection has no
        # acquired data, so it can never become evidence just by being in context.
        return self.usable_acquisition and self.context_visible is True

    @classmethod
    def from_content(
        cls,
        content: str,
        *,
        is_error: bool = False,
        context: str | None = None,
        skipped: bool = False,
        acquired: bool | None = None,
    ) -> EvidenceState:
        """Derive the evidence state.

        ``acquired`` lets a caller that already decoded the payload (context
        truncation does) pass the verdict in, avoiding a second full ``json.loads``
        of the same content. ``None`` means "not determined" and is decoded here.
        """
        if acquired is None:
            acquired = not is_error and has_meaningful_tool_content(content)
        else:
            acquired = bool(acquired) and not is_error
        # 上下文未被截断时（绝大多数结果），可见性与采集结果必然相同。
        # 此前无条件再解析一次同一份 JSON：一个 9k 字符的结果约 115µs，
        # 一次请求几十条工具结果就是数毫秒的纯重复解码。
        if context is None:
            visible = None
        elif context == content:
            visible = acquired
        else:
            visible = acquired and has_meaningful_tool_content(context)
        return cls(acquired, visible, is_error, skipped)


@dataclass(frozen=True, slots=True)
class StopReason:
    code: str
    description: str
    retain_acquired_evidence: bool = False
    fatal: bool = False


# Single source of truth for execution stop categories (no provider error bodies).
_STOP_REASONS = {
    item.code: item
    for item in (
        StopReason("", "结束原因未提供"),
        StopReason("stop", "模型正常结束"),
        StopReason("tool_calls", "模型请求工具调用"),
        StopReason("length", "模型输出达到长度上限", True),
        StopReason("stream_error", "模型流式响应中断或缺少结束帧", True),
        StopReason("empty_response", "模型未返回有效摘要", True),
        StopReason("invalid_tool_call_output", "模型未生成有效结论", True),
        StopReason("insufficient_evidence", "尚未获得可用于回答的有效证据", True),
        StopReason("generation_timeout", "分析时间预算已耗尽", True),
        StopReason("tool_budget_exceeded", "工具调用预算已用尽", True),
        StopReason("tool_context_budget_exhausted", "证据上下文预算已用尽", True),
        StopReason("dependency_unavailable", "上游分析未形成可用证据"),
        StopReason("execution_error", "分析任务执行失败"),
        StopReason("content_filter", "模型内容过滤终止输出", fatal=True),
        StopReason("invalid_response", "模型接口格式不兼容", fatal=True),
        StopReason("generation_error", "模型生成失败", fatal=True),
        StopReason("bad_request", "模型请求参数不被上游接受", fatal=True),
        StopReason("authentication_error", "模型认证失败，请检查 API Key", fatal=True),
        StopReason("permission_error", "模型访问权限不足", fatal=True),
        StopReason("rate_limited", "模型服务限流", fatal=True),
        StopReason("unexpected_finish", "模型返回未知结束状态", fatal=True),
        StopReason("unknown", "未知执行结束原因", fatal=True),
    )
}


def stop_reason(code: str | None) -> StopReason:
    return _STOP_REASONS.get(code or "", _STOP_REASONS["unknown"])


def model_stop_code(finish_reason: str | None) -> str:
    if finish_reason is None:
        return "stop"  # Non-streaming compatibility; stream EOF is normalized earlier.
    if finish_reason in {"stop", "tool_calls", "length", "content_filter", "stream_error"}:
        return finish_reason
    return "unexpected_finish"


def result_status(
    *, has_output: bool, has_evidence: bool = False, failed: bool = False, incomplete: bool = False
) -> ExecutionStatus:
    if failed or not (has_output or has_evidence):
        return "failed"
    if incomplete or not has_output:
        return "partial"
    return "completed"


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    status: ExecutionStatus
    reason: StopReason
    has_output: bool
    has_evidence: bool

    @property
    def can_retain_acquired_evidence(self) -> bool:
        return self.has_evidence and self.reason.retain_acquired_evidence and not self.reason.fatal


def research_outcome(
    *,
    summary: str,
    has_evidence: bool,
    termination_reason: str,
    execution_status: ExecutionStatus | None = None,
    incomplete: bool = False,
) -> ExecutionOutcome:
    reason = stop_reason(termination_reason)
    # A failed generation can leave usable raw evidence for an explicitly
    # recoverable reason; that is a partial research product, never a full answer.
    recoverable_failure = has_evidence and reason.retain_acquired_evidence and not reason.fatal
    status = result_status(
        has_output=bool(summary.strip()),
        has_evidence=has_evidence,
        failed=reason.fatal or (execution_status == "failed" and not recoverable_failure),
        incomplete=incomplete or reason.retain_acquired_evidence or execution_status in {"partial", "failed"},
    )
    return ExecutionOutcome(status, reason, bool(summary.strip()), has_evidence)
