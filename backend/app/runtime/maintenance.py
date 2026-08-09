import time

from app.infrastructure.persistence import task_lease_store, twitter_store
from app.modules.bot.persistence import jobs as bot_jobs
from app.modules.bot.persistence import rate_limits as bot_rate_limits
from app.modules.quant.persistence import runs as quant_runs


def purge_expired_runtime_data(
    *,
    bot_job_retention_seconds: int,
    bot_rate_limit_window_seconds: int,
    twitter_post_retention_days: int,
    now: float | None = None,
) -> dict[str, int]:
    current_time = time.time() if now is None else now
    return {
        "bot_command_jobs": bot_jobs.purge_completed(
            bot_job_retention_seconds,
            now=current_time,
        ),
        "bot_rate_limit_events": bot_rate_limits.purge_expired(
            bot_rate_limit_window_seconds,
            now=current_time,
        ),
        "background_task_leases": task_lease_store.purge_expired_task_leases(
            now=current_time,
        ),
        "twitter_posts": twitter_store.purge_twitter_posts(
            twitter_post_retention_days,
            now=current_time,
        ),
        "quant_backtest_runs": quant_runs.purge_completed(now=current_time),
    }
