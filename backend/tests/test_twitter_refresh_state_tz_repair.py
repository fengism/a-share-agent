"""Market 迁移 14：修正 twitter 刷新状态迁移 5 回填的时区偏移。

迁移 5 用 ``strftime('%s', MAX(fetched_at))`` 回填 last_refreshed_at，但
fetched_at 是 localtime 文本而 SQLite 日期函数按 UTC 解析，回填值比真实
epoch 大一个本地 UTC 偏移。迁移 14 只把仍等于旧口径重算结果的行平移回
真实 epoch；已被 ``save_twitter_refresh``（time.time()）覆写过的行不动。
"""

import sqlite3
import time

from app.infrastructure.persistence import ddl, migrations


def _market_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    for statement in ddl.MARKET_TABLES:
        conn.execute(statement)
    return conn


def _local_utc_offset_seconds() -> int:
    return time.localtime().tm_gmtoff or 0


def _state_rows(conn: sqlite3.Connection) -> dict[str, float]:
    return {
        row["author"]: float(row["last_refreshed_at"])
        for row in conn.execute("SELECT author, last_refreshed_at FROM twitter_feed_refresh_state")
    }


def test_migration_repairs_only_backfill_artifact_rows() -> None:
    conn = _market_db()
    conn.execute(
        "INSERT INTO twitter_posts(title, url, author, fetched_at) VALUES ('t', 'u', 'A', '2026-10-22 10:00:00')"
    )
    artifact = float(
        conn.execute("SELECT strftime('%s', '2026-10-22 10:00:00')").fetchone()[0]
    )
    overwritten = artifact - 3600.0
    conn.executemany(
        "INSERT INTO twitter_feed_refresh_state(author, last_refreshed_at) VALUES (?, ?)",
        [("A", artifact), ("B", overwritten), ("C", 0.0)],
    )

    migrations.apply_migrations(conn, migrations.MARKET_MIGRATIONS)

    rows = _state_rows(conn)
    offset = _local_utc_offset_seconds()
    assert conn.execute("SELECT 1 FROM schema_migrations WHERE version = 14").fetchone() is not None
    assert rows["A"] == artifact - offset, "回填伪影行应被平移回真实 epoch"
    assert rows["B"] == overwritten, "已被 time.time() 覆写的行不得改动"
    assert rows["C"] == 0.0, "零值行（无推文回退）不得改动"


def test_repair_is_idempotent_and_checksum_stable() -> None:
    conn = _market_db()
    conn.execute(
        "INSERT INTO twitter_posts(title, url, author, fetched_at) VALUES ('t', 'u', 'A', '2026-10-22 10:00:00')"
    )
    artifact = float(
        conn.execute("SELECT strftime('%s', '2026-10-22 10:00:00')").fetchone()[0]
    )
    conn.execute(
        "INSERT INTO twitter_feed_refresh_state(author, last_refreshed_at) VALUES ('A', ?)",
        (artifact,),
    )

    migrations.apply_migrations(conn, migrations.MARKET_MIGRATIONS)
    first = _state_rows(conn)
    # 第二次执行会重新校验全部已应用迁移的 checksum（含未改动的迁移 5），
    # 任何定义漂移都会抛 RuntimeError。
    migrations.apply_migrations(conn, migrations.MARKET_MIGRATIONS)
    assert _state_rows(conn) == first, "重复应用不得再次平移"
    assert first["A"] == artifact - _local_utc_offset_seconds()
