"""Bot 持久化任务状态命令。"""

import re
from datetime import datetime

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.modules.bot.commands.base import BotCommand
from app.modules.bot.models import BotExecutionContext, BotMessage, BotResponse
from app.modules.bot.persistence import jobs as job_store

_STATUS_LABELS = {
    "pending": "等待中",
    "running": "执行中",
    "succeeded": "已完成",
    "failed": "失败",
}


def _job_line(job: job_store.BotJob) -> str:
    status = _STATUS_LABELS.get(job.status, job.status)
    command = job.command_name or "unknown"
    created_at = datetime.fromtimestamp(job.created_at).astimezone().strftime("%m-%d %H:%M")
    return f"- `{job.id[:8]}` /{command} · {status} · {job.attempts}/{job.max_attempts} · {created_at}"


class TaskCommand(BotCommand):
    name = "task"
    aliases = ("t", "任务", "进度")
    description = "查看最近任务或指定任务状态"
    usage = "/task [任务ID]"

    def validate_args(self, args: list[str]) -> str | None:
        if not args:
            return None
        if len(args) > 1 or re.fullmatch(r"[0-9a-fA-F]{4,32}", args[0]) is None:
            return "任务 ID 必须是 4 至 32 位十六进制字符"
        return None

    async def execute(
        self,
        message: BotMessage,
        args: list[str],
        context: BotExecutionContext,
    ) -> BotResponse:
        if not args:
            jobs = await call_blocking(
                job_store.list_recent_jobs,
                message.user_id,
                semaphore=database_semaphore,
            )
            if not jobs:
                return BotResponse(text="暂无可查询的任务。", title="任务状态")
            return BotResponse(
                text="最近任务：\n" + "\n".join(_job_line(job) for job in jobs),
                title="任务状态",
            )

        job_id_prefix = args[0].strip().lower()
        jobs = await call_blocking(
            job_store.find_jobs_by_id_prefix,
            message.user_id,
            job_id_prefix,
            semaphore=database_semaphore,
        )
        if not jobs:
            return BotResponse.error("未找到该任务，或任务不属于当前飞书用户")
        if len(jobs) > 1:
            return BotResponse.error("任务 ID 不唯一，请输入更长的 ID")

        job = jobs[0]
        lines = [_job_line(job)]
        if job.last_error:
            lines.append(f"- 最近错误：{job.last_error}")
        if job.status == "running":
            lines.append("- 任务仍在执行，完成后会自动回发结果")
        return BotResponse(text="\n".join(lines), title="任务详情")
