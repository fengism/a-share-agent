"""宏观解读持久化缓存：按 key 存取 LLM 输出，避免重复调用大模型。

存于 market 库（与 twitter_analysis_snapshots 同库），进程重启/多 worker 均命中。
"""

import json
import logging
import time

from app.infrastructure.persistence.connection import get_connection, unit_of_work

logger = logging.getLogger(__name__)


def load_macro_analysis(
    keys: list[str],
    *,
    max_age_seconds: int,
    now: float | None = None,
) -> dict[str, dict]:
    """批量读取未过期的宏观解读缓存，返回 ``{cache_key: result}``。"""
    if not keys:
        return {}
    cutoff = (time.time() if now is None else now) - max_age_seconds
    placeholders = ",".join("?" for _ in keys)
    rows = get_connection().execute(
        f"""
        SELECT cache_key, result_json
        FROM macro_analysis_cache
        WHERE cache_key IN ({placeholders}) AND generated_at > ?
        """,
        (*keys, cutoff),
    ).fetchall()
    result: dict[str, dict] = {}
    for row in rows:
        try:
            payload = json.loads(row["result_json"])
        except (TypeError, json.JSONDecodeError):
            logger.warning("宏观解读缓存损坏: key=%s", row["cache_key"])
            continue
        if isinstance(payload, dict):
            result[row["cache_key"]] = payload
    return result


def save_macro_analysis(
    entries: dict[str, dict],
    *,
    generated_at: float | None = None,
    retention_seconds: int | None = None,
) -> None:
    """批量写入宏观解读缓存（UPSERT），并按需清理过期记录。"""
    if not entries:
        return
    saved_at = time.time() if generated_at is None else generated_at
    with unit_of_work() as work:
        work.connection.executemany(
            """
            INSERT INTO macro_analysis_cache(cache_key, result_json, generated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                result_json = excluded.result_json,
                generated_at = excluded.generated_at
            """,
            [
                (key, json.dumps(payload, ensure_ascii=False, separators=(",", ":")), saved_at)
                for key, payload in entries.items()
            ],
        )
        if retention_seconds is not None:
            work.connection.execute(
                "DELETE FROM macro_analysis_cache WHERE generated_at <= ?",
                (saved_at - retention_seconds,),
            )


def purge_macro_analysis(retention_days: int, *, now: float | None = None) -> int:
    """删除超过保留期的宏观解读缓存，返回删除行数。"""
    cutoff = (time.time() if now is None else now) - retention_days * 24 * 60 * 60
    with unit_of_work() as work:
        cursor = work.connection.execute(
            "DELETE FROM macro_analysis_cache WHERE generated_at <= ?",
            (cutoff,),
        )
        return cursor.rowcount or 0
