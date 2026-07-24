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
        image_url     TEXT    NOT NULL DEFAULT '',
        fetched_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        UNIQUE(author, url)
    )
    """
)

# ── 账号系统：用户 / 会话 / 邀请 / 每用户私密配置 ──
TABLES.append(
    """
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT    NOT NULL UNIQUE,
        password_hash TEXT    NOT NULL,
        is_admin      INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """
)
TABLES.append(
    """
    CREATE TABLE IF NOT EXISTS auth_sessions (
        token_hash TEXT    PRIMARY KEY,
        user_id    INTEGER NOT NULL,
        created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        expires_at TEXT    NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """
)
TABLES.append(
    """
    CREATE TABLE IF NOT EXISTS invites (
        code       TEXT    PRIMARY KEY,
        created_by INTEGER NOT NULL,
        used_by    INTEGER,
        created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        expires_at TEXT,
        used_at    TEXT,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
    )
    """
)
TABLES.append(
    """
    CREATE TABLE IF NOT EXISTS user_config (
        user_id INTEGER NOT NULL,
        key     TEXT    NOT NULL,
        value   TEXT    NOT NULL DEFAULT '',
        PRIMARY KEY (user_id, key),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """
)
# ── 管理员签发的一次性密码重置令牌 ──
TABLES.append(
    """
    CREATE TABLE IF NOT EXISTS password_resets (
        token_hash TEXT    PRIMARY KEY,
        user_id    INTEGER NOT NULL,
        created_by INTEGER NOT NULL,
        created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        expires_at TEXT    NOT NULL,
        used_at    TEXT,
        FOREIGN KEY (user_id)    REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
    )
    """
)
