"""从请求上下文解析审计操作者。

放在 ``app.core`` 而不是 ``app.domain``：解析逻辑依赖 ``request_context`` 的
contextvars，而 ``app.domain`` 只能放纯值对象（否则 domain→core 会形成包级依赖环）。
"""

from __future__ import annotations

from app.core.request_context import (
    get_current_client_ip,
    get_current_user,
    get_current_user_agent,
)
from app.domain.audit import AuditActor


def current_audit_actor() -> AuditActor:
    """构造当前请求的操作者；无请求上下文时返回只带 IP/UA 的匿名 actor。"""
    user = get_current_user()
    if user is None:
        return AuditActor(
            ip_address=get_current_client_ip(),
            user_agent=get_current_user_agent(),
        )
    return AuditActor(
        user_id=int(user["id"]),
        username=str(user.get("username", "")),
        ip_address=get_current_client_ip(),
        user_agent=get_current_user_agent(),
    )
