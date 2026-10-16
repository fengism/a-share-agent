"""配置分组基础设施。

分组类用**扁平字段名**声明字段（如 ``llm_provider``），组合进 ``Settings`` 后
仍是扁平字段，因此 ``.env`` / 数据库 / 配置 API / mypy 全部零改动。

同时提供 :class:`GroupView`，让代码可以按领域嵌套读写同一批字段：

    settings.llm.provider          # -> settings.llm_provider
    settings.push.feishu_webhook_url
    settings.llm.provider = "openai"

嵌套视图只是便捷入口，底层仍是扁平存储，不引入第二份状态。
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict


class ConfigGroup(BaseModel):
    """配置分组基类：声明本组字段的扁平名前缀，用于嵌套视图解析。"""

    model_config = ConfigDict(extra="ignore")

    PREFIX: ClassVar[str] = ""


class GroupView:
    """某个配置分组的嵌套读写视图（属性名 = 扁平名去掉组前缀）。"""

    __slots__ = ("_settings", "_prefix", "_fields")

    def __init__(self, settings: Any, group: type[ConfigGroup]) -> None:
        object.__setattr__(self, "_settings", settings)
        object.__setattr__(self, "_prefix", group.PREFIX)
        object.__setattr__(self, "_fields", frozenset(group.model_fields))

    def _resolve(self, attr: str) -> str:
        prefix = object.__getattribute__(self, "_prefix")
        fields = object.__getattribute__(self, "_fields")
        if prefix and f"{prefix}{attr}" in fields:
            return f"{prefix}{attr}"
        if attr in fields:
            return attr
        raise AttributeError(f"{attr!r} 不属于该配置分组")

    def __getattr__(self, attr: str) -> Any:
        return getattr(object.__getattribute__(self, "_settings"), self._resolve(attr))

    def __setattr__(self, attr: str, value: Any) -> None:
        setattr(object.__getattribute__(self, "_settings"), self._resolve(attr), value)

    def as_dict(self) -> dict[str, Any]:
        settings = object.__getattribute__(self, "_settings")
        return {name: getattr(settings, name) for name in sorted(object.__getattribute__(self, "_fields"))}
