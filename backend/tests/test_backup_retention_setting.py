"""数据库备份保留份数配置：可持久化、可热更新、越界被拒。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.configuration import PERSISTED_GLOBAL_KEYS, Settings, get_settings, update_settings
from app.modules.settings.schemas import ConfigResponse, ConfigUpdateRequest


def test_backup_retention_is_a_persisted_global_setting() -> None:
    """必须是全局可编辑项，否则前端保存后重启即丢失。"""
    assert "database_backup_retention_count" in PERSISTED_GLOBAL_KEYS
    assert "database_backup_retention_count" in ConfigUpdateRequest.model_fields
    assert "database_backup_retention_count" in ConfigResponse.model_fields


def test_backup_retention_applies_without_restart() -> None:
    original = get_settings().database_backup_retention_count
    try:
        updated = update_settings({"database_backup_retention_count": 5})
        assert updated.database_backup_retention_count == 5
        # 后台备份任务每轮重新 get_settings()，因此下一轮即生效
        assert get_settings().database_backup_retention_count == 5
    finally:
        update_settings({"database_backup_retention_count": original})
    assert get_settings().database_backup_retention_count == original


@pytest.mark.parametrize("value", [0, 91, -1])
def test_backup_retention_rejects_out_of_range(value: int) -> None:
    with pytest.raises(ValidationError):
        ConfigUpdateRequest(database_backup_retention_count=value)


@pytest.mark.parametrize("value", [1, 2, 90])
def test_backup_retention_accepts_boundary_values(value: int) -> None:
    assert ConfigUpdateRequest(database_backup_retention_count=value).database_backup_retention_count == value


def test_default_retention_is_two() -> None:
    """默认保留 2 份：market_daily 库 8.5 GB，份数直接换算成磁盘占用。"""
    assert Settings().database_backup_retention_count == 2
    assert get_settings().database_backup_retention_count == 2
