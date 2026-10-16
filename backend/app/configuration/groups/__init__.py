"""配置分组：把 Settings 的扁平字段按领域拆到独立模块。"""

from __future__ import annotations

from app.configuration.groups.base import ConfigGroup, GroupView
from app.configuration.groups.bot import BotGroup
from app.configuration.groups.data import DataSourceGroup, NetworkGroup
from app.configuration.groups.integrations import (
    FeishuGroup,
    IwencaiGroup,
    NotionGroup,
    PushGroup,
)
from app.configuration.groups.llm import LLMGroup
from app.configuration.groups.maintenance import MaintenanceGroup
from app.configuration.groups.research import ResearchGroup
from app.configuration.groups.runtime import RuntimeGroup

# 组合进 Settings 的顺序（字段最终仍是扁平访问）
CONFIG_GROUPS = (
    LLMGroup,
    FeishuGroup,
    PushGroup,
    NotionGroup,
    IwencaiGroup,
    BotGroup,
    DataSourceGroup,
    NetworkGroup,
    MaintenanceGroup,
    ResearchGroup,
    RuntimeGroup,
)

__all__ = [
    "CONFIG_GROUPS",
    "BotGroup",
    "ConfigGroup",
    "DataSourceGroup",
    "FeishuGroup",
    "GroupView",
    "IwencaiGroup",
    "LLMGroup",
    "MaintenanceGroup",
    "NetworkGroup",
    "NotionGroup",
    "PushGroup",
    "ResearchGroup",
    "RuntimeGroup",
]
