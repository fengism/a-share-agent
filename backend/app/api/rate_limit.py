"""按用户维度的请求频率限制（LLM 触发型端点）。

**为什么需要**：LLM 端点存在「用户 Key → 全局 Key」回退，且共享进程级的
``max_concurrent_llm_requests`` 信号量。没有频率上限时，单个账号就能反复触发
长任务：既烧掉管理员配置的全局额度，也会把全局槽位占满，让其他用户全部排队
（表现为「服务变慢」而不是「某个人被限流」，很难归因）。

**为什么放在 API 层**：限流是接入策略而非领域规则 —— 同一份 ``generate_daily_review``
既被 HTTP 触发也被定时任务触发，后台任务不该受用户频率上限约束。因此做成路由依赖
（``dependencies=[Depends(llm_rate_limit)]``）而不是包在 service 里。

**为什么不用 middleware**：认证是 FastAPI 依赖（``require_active_user``），middleware
运行在依赖之前、拿不到用户身份。依赖注入还自带同请求去重，不会重复计数。

**实现**：滑动窗口（复用 bot 侧同款思路，但独立实例，避免 bot 调参影响 HTTP）。
键为 ``(user_id, bucket)``，随用户数增长；每 ``_PURGE_INTERVAL`` 次计数顺带清理过期键，
因此字典不会无限膨胀（对照本仓库 ``_recent_dispatches`` 只写不删的老问题）。

**多进程限制**：计数在进程内（与 ``max_concurrent_llm_requests`` 等既有并发保护一致），
``uvicorn --workers N`` 下等效上限是 ``N × limit``。本项目默认单 worker；若要严格
跨进程限额，需要把计数挪到共享存储（Redis/SQLite），那是另一个量级的改动。
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Depends

from app.api.auth.dependencies import require_active_user
from app.api.errors import TooManyRequestsError
from app.configuration import get_settings
from app.domain.identity import AuthenticatedUser

#: 惰性清理的触发间隔（次数）。清理本身是 O(键数)，不需要每次请求都做。
_PURGE_INTERVAL = 256

_LOCK = threading.Lock()
_HITS: dict[tuple[int, str], deque[float]] = defaultdict(deque)
_CALLS_SINCE_PURGE = 0


def reset_llm_rate_limit() -> None:
    """清空所有计数（测试与配置变更后调用）。"""
    global _CALLS_SINCE_PURGE
    with _LOCK:
        _HITS.clear()
        _CALLS_SINCE_PURGE = 0


def _purge_expired(now: float, window: float) -> None:
    """移除窗口内已无记录的键（调用方已持锁）。"""
    deadline = now - window
    for key in [k for k, hits in _HITS.items() if not hits or hits[-1] <= deadline]:
        del _HITS[key]


def check_and_record(
    user_id: int,
    *,
    limit: int,
    window: float,
    bucket: str = "llm",
    clock: Callable[[], float] = time.monotonic,
) -> int | None:
    """记录一次请求；放行返回 ``None``，超限返回建议的 ``Retry-After`` 秒数。

    Param:
        user_id: 已认证用户 id（来自 ``require_active_user``）。
        limit: 窗口内允许的最大请求数。
        window: 窗口长度（秒）。
        bucket: 限流分桶名，便于以后给不同端点不同额度。
        clock: 时钟注入，测试用。
    Return:
        ``None`` = 放行；``int`` = 超限，值为距离窗口释放还有多少秒（向上取整，至少 1）。
    """
    global _CALLS_SINCE_PURGE
    now = clock()
    window_start = now - window
    key = (user_id, bucket)
    with _LOCK:
        _CALLS_SINCE_PURGE += 1
        if _CALLS_SINCE_PURGE >= _PURGE_INTERVAL:
            _purge_expired(now, window)
            _CALLS_SINCE_PURGE = 0
        hits = _HITS[key]
        while hits and hits[0] <= window_start:
            hits.popleft()
        if len(hits) >= limit:
            # hits[0] 是窗口内最早的一次；它过期后名额才释放。
            retry_after = int(hits[0] + window - now) + 1
            return max(1, retry_after)
        hits.append(now)
        return None


async def llm_rate_limit(user: AuthenticatedUser = Depends(require_active_user)) -> None:
    """LLM 触发型端点的每用户频率门禁。

    依赖 ``require_active_user``：FastAPI 会复用同一次请求里已解析的身份，
    因此挂在路由上不会重复查库。

    Raise:
        TooManyRequestsError: 超出 ``user_llm_rate_limit_requests`` 窗口额度。
    """
    settings = get_settings()
    limit = max(1, settings.user_llm_rate_limit_requests)
    window = max(1, settings.user_llm_rate_limit_window)
    retry_after = check_and_record(int(user["id"]), limit=limit, window=window)
    if retry_after is not None:
        raise TooManyRequestsError(
            f"操作过于频繁（每 {window} 秒最多 {limit} 次），请 {retry_after} 秒后重试",
            code="llm.rate_limited",
            retry_after_seconds=retry_after,
        )


__all__ = ["check_and_record", "llm_rate_limit", "reset_llm_rate_limit"]
