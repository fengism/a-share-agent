"""审计留痕的跨层模型。

管理员敏感操作（改角色、禁用、删除、发重置链接、创建/吊销邀请码、修改全局配置）
需要能回答"谁在什么时候、从哪个 IP、对谁做了什么"。这里只定义不可变的值对象，
具体落库在 ``app.infrastructure.persistence.admin_audit_store``。

本模块刻意**不依赖** ``app.core``：``app.domain`` 只放纯值对象，操作者解析逻辑
（读请求上下文）在 ``app.core.audit``，避免 domain→core 形成包级依赖环。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuditActor:
    """审计事件的操作者。后台任务 / CLI 场景下 ``user_id`` 为 None。"""

    user_id: int | None = None
    username: str = ""
    ip_address: str = ""
    user_agent: str = ""

    @property
    def is_anonymous(self) -> bool:
        return self.user_id is None

    def as_dict(self) -> dict[str, object]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


ANONYMOUS_ACTOR = AuditActor()
