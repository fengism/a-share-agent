"""通知投递审计与历史记录持久化。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.configuration.paths import DATA_DIR
from app.infrastructure.persistence.json_storage import atomic_write_text

logger = logging.getLogger(__name__)

_HISTORY_FILE = DATA_DIR / "notification_history.json"
_MAX_HISTORY_ENTRIES = 100
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class NotificationDeliveryRecord(BaseModel):
    """单次通知投递记录。"""

    id: str
    timestamp: str
    category: str
    title: str
    summary: str
    severity: str
    channels: dict[str, dict[str, Any]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


def load_notification_history(limit: int = 50) -> list[NotificationDeliveryRecord]:
    """读取最近的通知投递记录。"""
    try:
        if not _HISTORY_FILE.exists():
            return []
        with _HISTORY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        records = [NotificationDeliveryRecord.model_validate(item) for item in data]
        return records[:limit]
    except Exception as exc:
        logger.warning("读取通知历史记录失败: %s", exc)
        return []


def record_notification_delivery(
    category: str,
    title: str,
    summary: str,
    severity: str,
    channels: dict[str, dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> NotificationDeliveryRecord:
    """追加单次通知投递记录，自动截断保留最近 100 条。"""
    now = datetime.now(_SHANGHAI_TZ).isoformat(timespec="seconds")
    record_id = f"notif_{int(datetime.now().timestamp() * 1000)}"

    record = NotificationDeliveryRecord(
        id=record_id,
        timestamp=now,
        category=category,
        title=title,
        summary=summary,
        severity=severity,
        channels=channels,
        metadata=metadata or {},
    )

    try:
        existing = load_notification_history(limit=_MAX_HISTORY_ENTRIES)
        updated = [record] + [r for r in existing if r.id != record.id][: _MAX_HISTORY_ENTRIES - 1]
        payload = [r.model_dump(mode="json") for r in updated]
        atomic_write_text(_HISTORY_FILE, json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception as exc:
        logger.warning("写入通知历史记录失败: %s", exc)

    return record


def clear_notification_history() -> bool:
    """清空所有通知投递审计记录。"""
    try:
        if _HISTORY_FILE.exists():
            atomic_write_text(_HISTORY_FILE, json.dumps([], ensure_ascii=False))
        return True
    except Exception as exc:
        logger.warning("清空通知历史记录失败: %s", exc)
        return False
