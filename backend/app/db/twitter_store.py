import logging
from datetime import datetime, timedelta

from app.db.connection import get_connection

logger = logging.getLogger(__name__)

_REFRESH_MINUTES = 5


def save_twitter_posts(posts: list[dict]) -> None:
    """批量写入 Twitter 推文/文章，重复 (author, url) 自动忽略。

    Param:
        posts: 包含 title、content、source、publish_time、url、author 等字段的字典列表。
    Return:
        无。
    """
    conn = get_connection()
    rows = [
        (
            p.get("title", ""),
            p.get("content", ""),
            p.get("publish_time", ""),
            p.get("url", ""),
            p.get("author", ""),
        )
        for p in posts
        if p.get("url") and p.get("author")
    ]
    if not rows:
        return
    conn.executemany(
        "INSERT OR IGNORE INTO twitter_posts "
        "(title, content, publish_time, url, author) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    logger.info(f"写入 Twitter 数据: rows={len(rows)}, authors={set(p.get('author','') for p in posts)}")


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
        f"""SELECT title, content, source, publish_time, url, author, read_count, comment_count
            FROM twitter_posts
            WHERE author IN ({placeholders})
            ORDER BY publish_time DESC
            LIMIT ?""",
        (*authors, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_stale_authors(authors: list[str]) -> list[str]:
    """返回需要刷新的作者列表（超过 _REFRESH_MINUTES 未更新）。

    Param:
        authors: 配置中的全部作者列表。
    Return:
        需要刷新的作者列表。
    """
    if not authors:
        return []
    conn = get_connection()
    placeholders = ",".join("?" for _ in authors)
    cutoff = (datetime.now() - timedelta(minutes=_REFRESH_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.execute(
        f"""SELECT author
            FROM twitter_posts
            WHERE author IN ({placeholders})
            GROUP BY author
            HAVING MAX(fetched_at) > ?""",
        (*authors, cutoff),
    )
    fresh = {row["author"] for row in cursor.fetchall()}
    stale = [a for a in authors if a not in fresh]
    return stale
