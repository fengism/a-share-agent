"""产业链存档应用服务。"""

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.modules.industry_chain.models import IndustryChainResult
from app.modules.industry_chain.persistence import repository
from app.modules.industry_chain.schemas import IndustryChainHistoryItem, IndustryChainLatestResponse


def load_industry_chain(name: str, archive_id: str, user_id: int) -> IndustryChainResult | None:
    """同步读取产业链存档，供同步业务流程复用。"""
    return repository.load_industry_chain(name, archive_id, user_id)


async def list_industry_chain_history(
    user_id: int,
    *,
    name: str | None,
    limit: int,
    offset: int,
    can_delete_legacy: bool,
) -> list[IndustryChainHistoryItem]:
    return await call_blocking(
        repository.list_industry_chains,
        user_id,
        name,
        limit,
        offset,
        can_delete_legacy,
        semaphore=misc_semaphore,
    )


async def get_latest_industry_chain_archive(
    name: str,
    user_id: int,
    *,
    can_delete_legacy: bool,
) -> IndustryChainLatestResponse:
    items = await list_industry_chain_history(
        user_id,
        name=name,
        limit=1,
        offset=0,
        can_delete_legacy=can_delete_legacy,
    )
    if not items:
        return IndustryChainLatestResponse(archive_id="")
    return IndustryChainLatestResponse(
        archive_id=items[0].archive_id,
        saved_at=items[0].saved_at,
    )


async def load_industry_chain_archive(
    name: str,
    archive_id: str,
    user_id: int,
) -> IndustryChainResult | None:
    return await call_blocking(
        repository.load_industry_chain,
        name,
        archive_id,
        user_id,
        semaphore=misc_semaphore,
    )


async def remove_industry_chain_archive(
    name: str,
    archive_id: str,
    user_id: int,
    *,
    can_delete_legacy: bool,
) -> bool:
    return await call_blocking(
        repository.delete_industry_chain,
        name,
        archive_id,
        user_id,
        can_delete_legacy,
        semaphore=misc_semaphore,
    )
