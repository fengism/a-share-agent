"""Bot 单个持久化任务的入队与执行。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.configuration import get_settings
from app.configuration.schema import Settings
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.core.metrics import metrics
from app.modules.bot.job_execution import execute_bot_job
from app.modules.bot.models import BotMessage
from app.modules.bot.persistence import jobs as job_store
from app.modules.bot.platforms.registry import get_bot_platform
from app.modules.bot.service import get_bot_service

logger = logging.getLogger(__name__)
_COMMAND_ALIASES = {
    "a": "analyze",
    "分析": "analyze",
    "查": "analyze",
    "m": "market",
    "大盘": "market",
    "复盘": "market",
    "b": "batch",
    "批量": "batch",
    "t": "task",
    "任务": "task",
    "进度": "task",
}


def _serialize_message(message: BotMessage) -> dict[str, Any]:
    return {
        "platform": message.platform,
        "message_id": message.message_id,
        "event_id": message.event_id,
        "user_id": message.user_id,
        "user_name": message.user_name,
        "chat_id": message.chat_id,
        "chat_type": message.chat_type,
        "content": message.content,
        "mentioned": message.mentioned,
        "timestamp": message.timestamp.isoformat(),
    }


def _deserialize_message(payload: dict[str, Any]) -> BotMessage:
    return BotMessage(
        platform=str(payload["platform"]),
        message_id=str(payload["message_id"]),
        event_id=str(payload["event_id"]),
        user_id=str(payload["user_id"]),
        user_name=str(payload["user_name"]),
        chat_id=str(payload["chat_id"]),
        chat_type=payload["chat_type"],
        content=str(payload["content"]),
        mentioned=bool(payload.get("mentioned", False)),
        timestamp=datetime.fromisoformat(str(payload["timestamp"])),
    )


def _command_name(content: str, command_prefix: str) -> str:
    text = content.strip()
    if text.startswith(command_prefix):
        text = text[len(command_prefix):].strip()
    token = text.partition(" ")[0].lower()
    if token in _COMMAND_ALIASES:
        return _COMMAND_ALIASES[token]
    for alias in sorted(
        (item for item in _COMMAND_ALIASES if not item.isascii()),
        key=len,
        reverse=True,
    ):
        if token.startswith(alias):
            return _COMMAND_ALIASES[alias]
    return token


async def enqueue_bot_message(
    message: BotMessage,
    *,
    settings_provider=get_settings,
    blocking_runner=call_blocking,
) -> bool:
    settings = settings_provider()
    event_id = message.event_id or message.message_id or uuid4().hex
    command_name = _command_name(message.content, settings.bot_command_prefix)
    enqueued = await blocking_runner(
        job_store.enqueue,
        event_id=event_id,
        platform=message.platform,
        message_payload=_serialize_message(message),
        max_attempts=settings.bot_job_max_attempts,
        dedup_ttl_seconds=settings.bot_event_dedup_ttl_seconds,
        request_user_id=message.user_id,
        command_name=command_name,
        semaphore=database_semaphore,
    )
    metrics.record_bot_event("enqueued" if enqueued else "duplicate")
    return enqueued


async def _renew_job_lease(
    job_id: str,
    owner_id: str,
    lease_seconds: int,
    *,
    blocking_runner=call_blocking,
) -> None:
    interval = max(1.0, lease_seconds / 3)
    while True:
        await asyncio.sleep(interval)
        try:
            renewed = await blocking_runner(
                job_store.renew_lease,
                job_id,
                owner_id,
                lease_seconds,
                semaphore=database_semaphore,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Bot 任务租约续期异常: job_id=%s owner=%s", job_id, owner_id)
            return
        if not renewed:
            logger.warning("Bot 任务租约续期失败: job_id=%s owner=%s", job_id, owner_id)
            return


async def process_next_bot_job(
    *,
    owner_id: str,
    settings_provider=get_settings,
    service_provider=get_bot_service,
    platform_provider=get_bot_platform,
    blocking_runner=call_blocking,
) -> bool:
    settings: Settings = settings_provider()
    job = await blocking_runner(
        job_store.claim_next,
        owner_id,
        settings.bot_job_lease_seconds,
        semaphore=database_semaphore,
    )
    if job is None:
        return False
    metrics.record_bot_event("claimed")

    heartbeat = asyncio.create_task(
        _renew_job_lease(
            job.id,
            owner_id,
            settings.bot_job_lease_seconds,
            blocking_runner=blocking_runner,
        ),
        name=f"bot_job_lease:{job.id}",
    )
    try:
        message = _deserialize_message(job.message_payload)
        await execute_bot_job(
            job,
            owner_id,
            message,
            platform_provider(message.platform),
            service_provider(),
            blocking_runner=blocking_runner,
        )
    except asyncio.CancelledError:
        await blocking_runner(
            job_store.release,
            job.id,
            owner_id,
            "CancelledError",
            semaphore=database_semaphore,
        )
        metrics.record_bot_event("released")
        raise
    except Exception as exc:
        retry_delay = settings.bot_job_retry_base_seconds * (2 ** max(0, job.attempts - 1))
        status = await blocking_runner(
            job_store.fail,
            job.id,
            owner_id,
            type(exc).__name__,
            retry_delay,
            semaphore=database_semaphore,
        )
        metrics.record_bot_event("retrying" if status == "pending" else "failed")
        logger.exception(
            "Bot 持久化任务执行失败: job_id=%s event_id=%s attempt=%s status=%s",
            job.id,
            job.event_id,
            job.attempts,
            status,
        )
    finally:
        heartbeat.cancel()
        await asyncio.gather(heartbeat, return_exceptions=True)
    return True
