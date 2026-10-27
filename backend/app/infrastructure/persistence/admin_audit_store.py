"""管理员操作审计存储。

与 ``login_audit_logs``（登录/注册事件）分开：那张表的语义是"认证事件"，
字段是 username/user_id/status；这里是"管理动作"，需要 actor + target + 变更内容。

**不要写入密钥类取值**：``details`` 只记录字段名与布尔/枚举类取值（例如
``{"fields": ["llm_api_key"], "is_admin": true}``），绝不落 API Key、密码、
代理口令等明文，否则审计表本身成了泄漏源。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.audit import current_audit_actor
from app.core.security import now_ts
from app.domain.audit import AuditActor
from app.infrastructure.persistence.connection import get_connection, unit_of_work
from app.infrastructure.persistence.retention import purge_rows_in_batches

logger = logging.getLogger(__name__)

_MAX_DETAILS_CHARS = 4000
_MAX_LABEL_CHARS = 128


def _connection():
    return get_connection("user")


def _encode_details(details: dict[str, Any] | None) -> str:
    if not details:
        return ""
    try:
        encoded = json.dumps(details, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):  # pragma: no cover - 兜底，避免审计写入失败影响业务
        logger.warning("审计详情无法序列化，已丢弃: keys=%s", sorted(details))
        return ""
    return encoded[:_MAX_DETAILS_CHARS]


def record_admin_action(
    *,
    action: str,
    target_type: str = "",
    target_id: str | int = "",
    target_label: str = "",
    details: dict[str, Any] | None = None,
    actor: AuditActor | None = None,
) -> None:
    """写入一条管理动作审计记录。

    业务成功之后调用；写入失败只记日志，不向上抛（审计不能把业务搞挂）。
    """
    resolved_actor = actor or current_audit_actor()
    try:
        with unit_of_work(connection=_connection(), immediate=True) as work:
            work.connection.execute(
                """
                INSERT INTO admin_audit_logs (
                    actor_id, actor_username, actor_ip, actor_user_agent,
                    action, target_type, target_id, target_label, details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_actor.user_id,
                    resolved_actor.username[:64],
                    resolved_actor.ip_address[:64],
                    resolved_actor.user_agent[:512],
                    action[:64],
                    target_type[:32],
                    str(target_id)[:64],
                    target_label[:_MAX_LABEL_CHARS],
                    _encode_details(details),
                    now_ts(),
                ),
            )
    except Exception:  # noqa: BLE001 - 审计写入失败绝不能把业务操作带崩
        logger.warning(
            "写入管理审计失败: action=%s target=%s/%s actor=%s",
            action,
            target_type,
            target_id,
            resolved_actor.user_id,
            exc_info=True,
        )


def list_admin_actions(
    *,
    limit: int = 50,
    offset: int = 0,
    action: str | None = None,
    actor_username: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    connection = _connection()
    where_clauses: list[str] = []
    params: list[Any] = []
    if action:
        where_clauses.append("action = ?")
        params.append(action)
    if actor_username:
        where_clauses.append("actor_username LIKE ?")
        params.append(f"%{actor_username}%")
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    total_row = connection.execute(
        f"SELECT COUNT(*) AS n FROM admin_audit_logs {where_sql}", params
    ).fetchone()
    total = int(total_row["n"]) if total_row else 0
    rows = connection.execute(
        f"""
        SELECT id, actor_id, actor_username, actor_ip, actor_user_agent,
               action, target_type, target_id, target_label, details, created_at
        FROM admin_audit_logs
        {where_sql}
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, max(1, limit), max(0, offset)),
    ).fetchall()
    return [dict(row) for row in rows], total


def purge_admin_actions(retention_days: int) -> int:
    """删除超过保留期的审计记录；``retention_days <= 0`` 表示永久保留。"""
    if retention_days <= 0:
        return 0
    from datetime import timedelta

    from app.domain.timezones import market_now

    cutoff = (market_now() - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")
    result = purge_rows_in_batches(
        _connection(),
        table_name="admin_audit_logs",
        predicate_sql="created_at < ?",
        parameters=(cutoff,),
        order_by="created_at, rowid",
    )
    return int(result.deleted)
