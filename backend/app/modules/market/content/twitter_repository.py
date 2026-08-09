"""Twitter 内容和分析快照的异步仓储边界。"""

from dataclasses import dataclass

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore, misc_semaphore
from app.infrastructure.persistence.twitter_store import (
    load_twitter_analysis_snapshot,
    save_twitter_analysis_snapshot,
)
from app.market_data.market.public import get_twitter_user_content


@dataclass(frozen=True)
class TwitterAnalysisSnapshotKey:
    username: str
    content_hash: str
    llm_provider: str
    llm_model: str
    prompt_version: str


class TwitterContentRepository:
    async def list_user_content(self, username: str) -> list[dict]:
        return await call_blocking(get_twitter_user_content, username, semaphore=misc_semaphore)


class TwitterAnalysisSnapshotRepository:
    async def load(self, key: TwitterAnalysisSnapshotKey, *, max_age_seconds: int) -> dict | None:
        return await call_blocking(
            load_twitter_analysis_snapshot,
            key.username,
            key.content_hash,
            key.llm_provider,
            key.llm_model,
            key.prompt_version,
            max_age_seconds=max_age_seconds,
            semaphore=database_semaphore,
        )

    async def save(
        self,
        key: TwitterAnalysisSnapshotKey,
        result: dict,
        *,
        retention_seconds: int,
    ) -> None:
        await call_blocking(
            save_twitter_analysis_snapshot,
            key.username,
            key.content_hash,
            key.llm_provider,
            key.llm_model,
            key.prompt_version,
            result,
            retention_seconds=retention_seconds,
            semaphore=database_semaphore,
        )
