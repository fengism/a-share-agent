"""Process-wide TTL cache for public, slow-changing tool results.

``SharedToolCache`` only deduplicates inside one ``AgentExecutionContext``, so two
users asking the same daily/static question seconds apart both hit the upstream.
``ToolPolicy`` already declares how long a result may be reused
(``cache_ttl_seconds`` + ``freshness``); this module finally honours that across
requests.

Eligibility is deliberately narrow:

- ``scope="user"`` results depend on private per-user configuration and must
  never be shared, so only ``scope="public"`` is admitted.
- ``freshness`` must be ``daily`` or ``static``; realtime/near_realtime data is
  never reused across requests.
- errors are never stored (one upstream blip must not become a traffic-wide
  outage), and oversized payloads are skipped so the cache cannot be used as an
  unbounded memory amplifier.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass

from app.agentic.protocol import ToolResultInfo
from app.agentic.runtime.metrics import metrics
from app.agentic.tools.contracts import ToolPolicy

# The policy vocabulary these two sets come from; kept explicit so a new
# freshness value must be classified instead of silently becoming cacheable.
CROSS_REQUEST_FRESHNESS = frozenset({"daily", "static"})
_DEFAULT_MAX_ENTRIES = 512
_MAX_ENTRY_CHARACTERS = 24_000
# 跨请求复用的硬上界，与 policy 声明无关。`freshness="static"` 的工具 ttl 可以到
# 3600s（如行业列表），但有些工具把“静态”当成了“差不多就行”（例如含 PE/PB 的
# 同行业对比）。错误声明在单请求去重时最多让一次对话看到旧值，跨请求后就是全局
# 陈旧；这里统一压到 15 分钟，把任何错声明的炸开半径钉住。
_MAX_CROSS_REQUEST_TTL_SECONDS = 900.0


@dataclass
class _ProcessCacheEntry:
    result: ToolResultInfo
    expires_at: float


class ProcessToolCache:
    """Bounded TTL cache shared by every request in this process."""

    def __init__(self, *, max_entries: int = _DEFAULT_MAX_ENTRIES) -> None:
        self._entries: OrderedDict[str, _ProcessCacheEntry] = OrderedDict()
        self._max_entries = max(1, int(max_entries))

    @staticmethod
    def eligible(policy: ToolPolicy) -> bool:
        return (
            policy.scope == "public"
            and policy.freshness in CROSS_REQUEST_FRESHNESS
            and policy.cache_ttl_seconds > 0
            # 批内都不允许合并的调用（副作用工具）绝不能跨请求复用。
            # 这是对未来把 ttl>0 建到变更类工具上的防守：宁可少命中，不能把
            # 一次“下单/写配置”的回答从上一个请求里抬回来。
            and policy.deduplicate_in_batch
        )

    def get(self, key: str, tool_call_id: str) -> ToolResultInfo | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= time.monotonic():
            self._entries.pop(key, None)
            metrics.record_agentic_event("tool_process_cache_expired")
            return None
        # Touch for LRU recency, then hand back a per-call copy: tool_call_id is
        # part of the response contract and must match the caller's request.
        self._entries.move_to_end(key)
        metrics.record_agentic_event("tool_process_cache_hit")
        return ToolResultInfo(
            tool_call_id=tool_call_id,
            name=entry.result.name,
            content=entry.result.content,
            is_error=entry.result.is_error,
        )

    def put(self, key: str, result: ToolResultInfo, ttl_seconds: float) -> None:
        if result.is_error or ttl_seconds <= 0:
            return
        if len(result.content) > _MAX_ENTRY_CHARACTERS:
            metrics.record_agentic_event("tool_process_cache_skipped")
            return
        bounded_ttl = min(float(ttl_seconds), _MAX_CROSS_REQUEST_TTL_SECONDS)
        self._entries[key] = _ProcessCacheEntry(
            result=ToolResultInfo(
                tool_call_id=result.tool_call_id,
                name=result.name,
                content=result.content,
                is_error=result.is_error,
            ),
            expires_at=time.monotonic() + bounded_ttl,
        )
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
        metrics.record_agentic_event("tool_process_cache_store")

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


process_tool_cache = ProcessToolCache()

__all__ = [
    "CROSS_REQUEST_FRESHNESS",
    "ProcessToolCache",
    "process_tool_cache",
]