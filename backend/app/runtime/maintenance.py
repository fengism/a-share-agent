import time
from collections.abc import Callable
from time import perf_counter

from app.core.metrics import metrics
from app.infrastructure.persistence import task_lease_store, twitter_store
from app.infrastructure.persistence.retention import PurgeResult
from app.infrastructure.persistence.workflow_jobs import workflow_job_store
from app.modules.bot.persistence import jobs as bot_jobs
from app.modules.bot.persistence import rate_limits as bot_rate_limits
from app.modules.quant.persistence import runs as quant_runs


def _run_cleanup(
    database: str,
    name: str,
    cleanup: Callable[[], PurgeResult],
) -> int:
    started_at = perf_counter()
    try:
        result = cleanup()
    except Exception as error:
        metrics.record_persistence_operation(
            database,
            f"retention.{name}",
            success=False,
            duration_ms=(perf_counter() - started_at) * 1000,
            error_type=type(error).__name__,
        )
        raise
    metrics.record_persistence_operation(
        database,
        f"retention.{name}",
        success=True,
        duration_ms=(perf_counter() - started_at) * 1000,
        processed=result.deleted,
        pending=result.has_more,
    )
    return result.deleted


def purge_expired_auth_data() -> dict[str, int]:
    from app.infrastructure.persistence.session_store import purge_expired_with_status

    started_at = perf_counter()
    try:
        results = purge_expired_with_status()
    except Exception as error:
        metrics.record_persistence_operation(
            "user",
            "retention.auth",
            success=False,
            duration_ms=(perf_counter() - started_at) * 1000,
            error_type=type(error).__name__,
        )
        raise
    duration_ms = (perf_counter() - started_at) * 1000
    for name, result in results.items():
        metrics.record_persistence_operation(
            "user",
            f"retention.{name}",
            success=True,
            duration_ms=duration_ms,
            processed=result.deleted,
            pending=result.has_more,
        )
    return {name: result.deleted for name, result in results.items()}


def purge_expired_runtime_data(
    *,
    bot_job_retention_seconds: int,
    bot_rate_limit_window_seconds: int,
    twitter_post_retention_days: int,
    workflow_job_retention_seconds: int,
    now: float | None = None,
) -> dict[str, int]:
    current_time = time.time() if now is None else now
    return {
        "bot_command_jobs": _run_cleanup(
            "user",
            "bot_command_jobs",
            lambda: bot_jobs.purge_completed_with_status(
                bot_job_retention_seconds,
                now=current_time,
            ),
        ),
        "bot_rate_limit_events": _run_cleanup(
            "user",
            "bot_rate_limit_events",
            lambda: bot_rate_limits.purge_expired_with_status(
                bot_rate_limit_window_seconds,
                now=current_time,
            ),
        ),
        "background_task_leases": _run_cleanup(
            "market",
            "background_task_leases",
            lambda: task_lease_store.purge_expired_task_leases_with_status(now=current_time),
        ),
        "twitter_posts": _run_cleanup(
            "market",
            "twitter_posts",
            lambda: twitter_store.purge_twitter_posts_with_status(
                twitter_post_retention_days,
                now=current_time,
            ),
        ),
        "quant_backtest_runs": _run_cleanup(
            "user",
            "quant_backtest_runs",
            lambda: quant_runs.purge_completed_with_status(now=current_time),
        ),
        "workflow_jobs": _run_cleanup(
            "user",
            "workflow_jobs",
            lambda: workflow_job_store.purge_completed_with_status(
                workflow_job_retention_seconds,
                now=current_time,
            ),
        ),
    }


def purge_expired_file_data(
    *,
    potential_retention_days: int,
    valuation_snapshot_retention_days: int,
    analysis_archive_retention_days: int,
    industry_chain_retention_days: int,
    now: float | None = None,
) -> dict[str, int]:
    """清理按日累积的 JSON 快照与带历史索引的嵌套归档，避免 data 目录无限增长。

    扁平快照按文件 mtime 删除；``analyses`` / ``industry_chains`` 以「目录」为
    删除单位并在删除后重建历史索引，避免索引与文件不一致。
    """
    from app.configuration.paths import DATA_DIR
    from app.infrastructure.persistence.file_retention import purge_old_files
    from app.modules.analysis.persistence import repository as analysis_repository
    from app.modules.industry_chain.persistence import repository as industry_chain_repository

    current = time.time() if now is None else now
    return {
        "potential_stocks": purge_old_files(
            DATA_DIR / "potential_stocks",
            keep_days=potential_retention_days,
            now=current,
        ),
        "potential_performance": purge_old_files(
            DATA_DIR / "potential_performance",
            keep_days=potential_retention_days,
            now=current,
        ),
        "valuation_snapshots": purge_old_files(
            DATA_DIR / "valuation_snapshots",
            keep_days=valuation_snapshot_retention_days,
            now=current,
        ),
        "analysis_archives": analysis_repository.purge_expired_analysis_archives(
            analysis_archive_retention_days,
            now=current,
        ),
        "industry_chain_archives": industry_chain_repository.purge_expired_industry_chain_archives(
            industry_chain_retention_days,
            now=current,
        ),
    }
