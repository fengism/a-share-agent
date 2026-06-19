"""
所有表的 DDL 定义。新增数据类型只需追加建表语句。
"""

TABLES = [
    # ── 北向资金（沪深股通）分钟级流向 ──
    """
    CREATE TABLE IF NOT EXISTS hsgt_flow (
        date       TEXT    NOT NULL,  -- YYYY-MM-DD
        time       TEXT    NOT NULL,  -- HH:mm
        hgt        REAL,             -- 沪股通累计净买入（亿元）
        sgt        REAL,             -- 深股通累计净买入（亿元）
        total      REAL,             -- 合计
        updated_at TEXT,
        PRIMARY KEY (date, time)
    )
    """,
    # ── 每日行情快照（指数 / 个股摘要，按需扩展） ──
    """
    CREATE TABLE IF NOT EXISTS market_daily (
        date       TEXT    NOT NULL,  -- YYYY-MM-DD
        code       TEXT    NOT NULL,  -- 股票/指数代码
        name       TEXT,
        close      REAL,
        change_pct REAL,
        volume     REAL,
        amount     REAL,
        extra      TEXT,             -- JSON 扩展字段
        PRIMARY KEY (date, code)
    )
    """,
    # ── 板块排名快照 ──
    """
    CREATE TABLE IF NOT EXISTS sector_rankings (
        date          TEXT NOT NULL,
        name          TEXT NOT NULL,
        change_pct    REAL,
        up_count      INTEGER,
        down_count    INTEGER,
        leader        TEXT,
        leader_change REAL,
        extra         TEXT,
        PRIMARY KEY (date, name)
    )
    """,
]

TABLES.append(
    """
    CREATE TABLE IF NOT EXISTS twitter_posts (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        title         TEXT    NOT NULL,
        content       TEXT    NOT NULL DEFAULT '',
        source        TEXT    NOT NULL DEFAULT 'Twitter',
        publish_time  TEXT    NOT NULL DEFAULT '',
        url           TEXT    NOT NULL,
        author        TEXT    NOT NULL DEFAULT '',
        read_count    INTEGER NOT NULL DEFAULT 0,
        comment_count INTEGER NOT NULL DEFAULT 0,
        fetched_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        UNIQUE(author, url)
    )
    """
)
