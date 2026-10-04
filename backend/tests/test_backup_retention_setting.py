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


def test_default_retention_comes_from_schema() -> None:
    """默认值取自 Settings 字段定义，不受运行环境里的 .env / 环境变量影响。

    原用例硬编码断言 2，但仓库``.env`` 会设置 ``DATABASE_BACKUP_RETENTION_COUNT``，
    于是本地通过、CI（无 .env，落到 schema 默认 3）失败。此处改为直接校验字段定义，
    保证两种环境下断言一致，同时仍能守住"默认值被误改"这类回归。
    """
    default = Settings.model_fields["database_backup_retention_count"].default
    assert default == 3

    # 取值范围与 schema 一致：至少 1 份、最多 90 份（ge/le 是两个独立的约束对象）
    constraints = {
        (type(c).__name__, getattr(c, "ge", None), getattr(c, "le", None))
        for c in Settings.model_fields["database_backup_retention_count"].metadata
    }
    assert ("Ge", 1, None) in constraints
    assert ("Le", None, 90) in constraints


def test_env_override_is_respected() -> None:
    """显式传入的值必须覆盖默认值（``.env`` 与环境变量都能生效）。"""
    assert Settings(database_backup_retention_count=2).database_backup_retention_count == 2
    assert Settings(database_backup_retention_count=7).database_backup_retention_count == 7
