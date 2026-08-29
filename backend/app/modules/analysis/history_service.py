"""分析历史记录应用服务。"""

from app.configuration import get_effective_settings
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.persistence import repository


def get_latest_analysis(code: str, user_id: int, *, cache_ttl: int = 14400) -> AnalysisResult | None:
    """同步读取最新分析，供同步业务流程复用。"""
    return repository.get_latest_analysis(code, user_id, cache_ttl=cache_ttl)


def get_analysis_by_date(code: str, date: str, user_id: int, *, cache_ttl: int = 14400) -> AnalysisResult | None:
    """同步读取指定日期分析，供同步业务流程复用。"""
    return repository.get_analysis_by_date(code, date, user_id, cache_ttl=cache_ttl)


async def load_latest_analysis(code: str, user_id: int) -> AnalysisResult | None:
    settings = get_effective_settings()
    return await call_blocking(
        repository.get_latest_analysis,
        code,
        user_id,
        cache_ttl=settings.cache_ttl_analysis,
        semaphore=misc_semaphore,
    )


async def list_all_analysis_history(
    user_id: int,
    *,
    limit: int,
    offset: int,
    can_delete_legacy: bool,
    query: str | None = None,
) -> list[dict]:
    return await call_blocking(
        repository.list_all_analyses,
        user_id,
        limit,
        offset,
        can_delete_legacy,
        query,
        semaphore=misc_semaphore,
    )


async def list_analysis_history(
    code: str,
    user_id: int,
    *,
    limit: int,
    offset: int,
    can_delete_legacy: bool,
) -> list[dict]:
    return await call_blocking(
        repository.list_analyses,
        code,
        user_id,
        limit,
        offset,
        can_delete_legacy,
        semaphore=misc_semaphore,
    )


async def load_analysis_history(code: str, date: str, user_id: int) -> AnalysisResult | None:
    settings = get_effective_settings()
    return await call_blocking(
        repository.get_analysis_by_date,
        code,
        date,
        user_id,
        cache_ttl=settings.cache_ttl_analysis,
        semaphore=misc_semaphore,
    )


async def remove_analysis_history(
    code: str,
    date: str,
    user_id: int,
    *,
    can_delete_legacy: bool,
) -> bool:
    return await call_blocking(
        repository.delete_analysis,
        code,
        date,
        user_id,
        can_delete_legacy,
        semaphore=misc_semaphore,
    )
