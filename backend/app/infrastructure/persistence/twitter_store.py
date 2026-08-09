import json
import logging
import time
from collections import Counter

from app.infrastructure.persistence.connection import get_connection, unit_of_work

logger = logging.getLogger(__name__)

TWITTER_REFRESH_INTERVAL_SECONDS = 12 * 60 * 60


def _post_rows(posts: list[dict]) -> list[tuple[str, str, str, str, str, str]]:
    return [
        (
            post.get("title", ""),
            post.get("content", ""),
            post.get("image_url", ""),
            post.get("publish_time", ""),
            post.get("url", ""),
            post.get("author", ""),
        )
        for post in posts
        if post.get("url") and post.get("author")
    ]


def _upsert_twitter_posts(connection, rows: list[tuple[str, str, str, str, str, str]]) -> None:
    if not rows:
        return
    connection.executemany(
        """
        INSERT INTO twitter_posts(title, content, image_url, publish_time, url, author)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(author, url) DO UPDATE SET
            title = excluded.title,
            content = excluded.content,
            image_url = excluded.image_url,
            publish_time = excluded.publish_time,
            fetched_at = datetime('now','localtime')
        """,
        rows,
    )


def save_twitter_posts(posts: list[dict]) -> None:
    """批量写入 Twitter 推文/文章，重复 (author, url) 自动更新。

    Param:
        posts: 包含 title、content、source、publish_time、url、author 等字段的字典列表。
    Return:
        无。
    """
    connection = get_connection()
    rows = _post_rows(posts)
    if not rows:
        return
    _upsert_twitter_posts(connection, rows)
    connection.commit()
    logger.info(f"写入 Twitter 数据: rows={len(rows)}, authors={set(p.get('author', '') for p in posts)}")


def save_twitter_refresh(authors: list[str], posts: list[dict], *, refreshed_at: float | None = None) -> None:
    """原子保存抓取结果，并记录每个请求账号的最后成功刷新时间。"""
    normalized_authors = list(dict.fromkeys(author.strip() for author in authors if author.strip()))
    rows = _post_rows(posts)
    with unit_of_work() as work:
        _upsert_twitter_posts(work.connection, rows)
        timestamp = time.time() if refreshed_at is None else refreshed_at
        work.connection.executemany(
            """
            INSERT INTO twitter_feed_refresh_state(author, last_refreshed_at)
            VALUES (?, ?)
            ON CONFLICT(author) DO UPDATE SET last_refreshed_at = excluded.last_refreshed_at
            """,
            [(author, timestamp) for author in normalized_authors],
        )
    post_counts = Counter(row[5] for row in rows)
    logger.info(
        "Twitter 刷新结果已保存: authors=%s post_counts=%s",
        normalized_authors,
        dict(post_counts),
    )


def query_twitter_posts_by_authors(authors: list[str], limit: int = 100) -> list[dict]:
    """查询指定作者的最新推文。

    Param:
        authors: 作者列表。
        limit: 最多返回的记录数。
    Return:
        字典列表，按 publish_time 降序排列。
    """
    if not authors:
        return []
    conn = get_connection()
    placeholders = ",".join("?" for _ in authors)
    cursor = conn.execute(
        f"""SELECT title, content, source, publish_time, url, author, read_count, comment_count, image_url
            FROM twitter_posts
            WHERE author IN ({placeholders})
            ORDER BY publish_time DESC
            LIMIT ?""",
        (*authors, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


def purge_twitter_posts(retention_days: int, *, now: float | None = None) -> int:
    if retention_days <= 0:
        return 0
    current_time = time.time() if now is None else now
    cutoff = current_time - retention_days * 24 * 60 * 60
    connection = get_connection()
    cursor = connection.execute(
        "DELETE FROM twitter_posts WHERE fetched_at <= datetime(?, 'unixepoch', 'localtime')",
        (cutoff,),
    )
    connection.commit()
    return cursor.rowcount


def load_twitter_analysis_snapshot(
    username: str,
    content_hash: str,
    llm_provider: str,
    llm_model: str,
    prompt_version: str,
    *,
    max_age_seconds: int,
    now: float | None = None,
) -> dict | None:
    """读取账号、内容、模型和 Prompt 版本完全匹配的分析快照。"""
    row = get_connection().execute(
        """
        SELECT result_json, generated_at
        FROM twitter_analysis_snapshots
        WHERE username = ?
          AND content_hash = ?
          AND llm_provider = ?
          AND llm_model = ?
          AND prompt_version = ?
        """,
        (username, content_hash, llm_provider, llm_model, prompt_version),
    ).fetchone()
    if row is None:
        return None
    cutoff = (time.time() if now is None else now) - max_age_seconds
    if float(row["generated_at"]) <= cutoff:
        return None
    try:
        result = json.loads(row["result_json"])
    except (TypeError, json.JSONDecodeError):
        logger.warning("Twitter 分析快照损坏: username=%s", username)
        return None
    return result if isinstance(result, dict) else None


def save_twitter_analysis_snapshot(
    username: str,
    content_hash: str,
    llm_provider: str,
    llm_model: str,
    prompt_version: str,
    result: dict,
    *,
    generated_at: float | None = None,
    retention_seconds: int | None = None,
) -> None:
    """原子保存分析快照，并按需清理已过期快照。"""
    snapshot_time = time.time() if generated_at is None else generated_at
    with unit_of_work() as work:
        work.connection.execute(
            """
            INSERT INTO twitter_analysis_snapshots(
                username, content_hash, llm_provider, llm_model, prompt_version, result_json, generated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username, content_hash, llm_provider, llm_model, prompt_version) DO UPDATE SET
                result_json = excluded.result_json,
                generated_at = excluded.generated_at
            """,
            (
                username,
                content_hash,
                llm_provider,
                llm_model,
                prompt_version,
                json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                snapshot_time,
            ),
        )
        if retention_seconds is not None:
            work.connection.execute(
                "DELETE FROM twitter_analysis_snapshots WHERE generated_at <= ?",
                (snapshot_time - retention_seconds,),
            )


def get_stale_authors(authors: list[str], *, now: float | None = None) -> list[str]:
    """返回超过 12 小时未成功刷新的作者列表。

    Param:
        authors: 配置中的全部作者列表。
    Return:
        需要刷新的作者列表。
    """
    normalized_authors = list(dict.fromkeys(author.strip() for author in authors if author.strip()))
    if not normalized_authors:
        return []
    connection = get_connection()
    placeholders = ",".join("?" for _ in normalized_authors)
    cutoff = (time.time() if now is None else now) - TWITTER_REFRESH_INTERVAL_SECONDS
    cursor = connection.execute(
        f"""SELECT author FROM twitter_feed_refresh_state
            WHERE author IN ({placeholders}) AND last_refreshed_at > ?""",
        (*normalized_authors, cutoff),
    )
    fresh = {row["author"] for row in cursor.fetchall()}
    stale = [author for author in normalized_authors if author not in fresh]
    return stale
