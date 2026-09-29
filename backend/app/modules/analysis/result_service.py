"""个股分析结果缓存与持久化。"""

from __future__ import annotations

import asyncio
import logging

from app.core.cache import analysis_cache as cache
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.persistence import repository as analysis_storage

logger = logging.getLogger(__name__)


class AnalysisArchiveError(RuntimeError):
    """模型已完成，但归档未成功；不能通过重跑整个研究来重试保存。"""


async def persist_analysis_result(
    result: AnalysisResult,
    *,
    user_id: int,
    cache_key: str,
    cache_ttl_seconds: int,
) -> None:
    for attempt in range(3):
        try:
            await call_blocking(
                analysis_storage.save_analysis, result, user_id, semaphore=misc_semaphore,
            )
            break
        except Exception as error:
            logger.warning("分析归档失败: attempt=%s error_type=%s", attempt + 1, type(error).__name__)
            if attempt == 2:
                raise AnalysisArchiveError("报告已生成，但保存失败（已重试 3 次），未标记研究完成。请检查存储后重试。") from error
            await asyncio.sleep(0.2 * (attempt + 1))
    cache.set(cache_key, result, ttl=cache_ttl_seconds)


__all__ = ["persist_analysis_result"]
