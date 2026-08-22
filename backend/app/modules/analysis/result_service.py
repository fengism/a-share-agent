"""个股分析结果缓存与持久化。"""

from __future__ import annotations

import logging

from app.core.cache import cache
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.persistence import repository as analysis_storage

logger = logging.getLogger(__name__)


async def persist_analysis_result(
    result: AnalysisResult,
    *,
    user_id: int,
    cache_key: str,
    cache_ttl_seconds: int,
) -> None:
    cache.set(cache_key, result, ttl=cache_ttl_seconds)
    try:
        await call_blocking(
            analysis_storage.save_analysis,
            result,
            user_id,
            semaphore=misc_semaphore,
        )
    except Exception as error:
        logger.warning("分析结果持久化失败: %s", error)


__all__ = ["persist_analysis_result"]
