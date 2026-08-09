"""所有表的 DDL 定义。新增数据类型只需追加建表语句。"""

MARKET_TABLES = [
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
]

MARKET_TABLES.append(
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

MARKET_TABLES.append(
    """
    CREATE TABLE IF NOT EXISTS twitter_analysis_snapshots (
        username       TEXT NOT NULL,
        content_hash   TEXT NOT NULL,
        llm_provider   TEXT NOT NULL,
        llm_model      TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        result_json    TEXT NOT NULL,
        generated_at   REAL NOT NULL,
        PRIMARY KEY (username, content_hash, llm_provider, llm_model, prompt_version)
    )
    """
)

# ── 账号系统：用户 / 会话 / 邀请 / 每用户私密配置 ──
USER_TABLES = []

USER_TABLES.append(
    """
    CREATE TABLE IF NOT EXISTS users (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        username             TEXT    NOT NULL UNIQUE,
        password_hash        TEXT    NOT NULL,
        is_admin             INTEGER NOT NULL DEFAULT 0,
        must_change_password INTEGER NOT NULL DEFAULT 0,
        created_at           TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """
)
USER_TABLES.append(
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
USER_TABLES.append(
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
USER_TABLES.append(
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
USER_TABLES.append(
    """
    CREATE TABLE IF NOT EXISTS global_config (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """
)
# ── 管理员签发的一次性密码重置令牌 ──
USER_TABLES.append(
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

USER_TABLES.extend(
    [
        """
        CREATE TABLE IF NOT EXISTS portfolio_positions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            stock_code TEXT    NOT NULL,
            stock_name TEXT    NOT NULL DEFAULT '',
            buy_price  REAL    NOT NULL CHECK (buy_price > 0),
            buy_time   TEXT    NOT NULL,
            shares     INTEGER NOT NULL CHECK (shares > 0),
            created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_portfolio_positions_user_time
        ON portfolio_positions(user_id, buy_time DESC, id DESC)
        """,
    ]
)

USER_TABLES.extend(
    [
        """
        CREATE TABLE IF NOT EXISTS quant_strategies (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            name        TEXT NOT NULL,
            config_json TEXT NOT NULL,
            created_at  REAL NOT NULL,
            updated_at  REAL NOT NULL,
            UNIQUE(user_id, name),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_quant_strategies_user_time
        ON quant_strategies(user_id, updated_at DESC)
        """,
        """
        CREATE TABLE IF NOT EXISTS quant_backtest_runs (
            id                  TEXT PRIMARY KEY,
            user_id             INTEGER NOT NULL,
            name                TEXT NOT NULL,
            request_json        TEXT NOT NULL,
            result_json         TEXT,
            input_snapshot_json TEXT,
            data_hash           TEXT,
            engine_version      TEXT,
            status              TEXT NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')),
            attempts            INTEGER NOT NULL DEFAULT 0,
            max_attempts        INTEGER NOT NULL DEFAULT 2,
            available_at        REAL NOT NULL,
            lease_owner         TEXT,
            lease_until         REAL,
            last_error          TEXT,
            created_at          REAL NOT NULL,
            updated_at          REAL NOT NULL,
            completed_at        REAL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_quant_backtest_runs_claim
        ON quant_backtest_runs(status, available_at, lease_until, created_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_quant_backtest_runs_user_time
        ON quant_backtest_runs(user_id, created_at DESC)
        """,
    ]
)

# ── 文件正文的 SQLite 摘要索引 ──
HISTORY_INDEX_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS history_index_state (
    kind         TEXT NOT NULL,
    storage_root TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (kind, storage_root)
)
"""

ANALYSIS_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS analysis_history_index (
    storage_root  TEXT    NOT NULL,
    scope_user_id INTEGER NOT NULL DEFAULT 0,
    stock_code    TEXT    NOT NULL,
    analysis_date TEXT    NOT NULL,
    stock_name    TEXT    NOT NULL DEFAULT '',
    current_price REAL,
    overall_rating REAL,
    signal        TEXT,
    confidence    REAL,
    file_path     TEXT    NOT NULL,
    PRIMARY KEY (storage_root, scope_user_id, stock_code, analysis_date)
)
"""
ANALYSIS_HISTORY_INDEXES = (
    """
    CREATE INDEX IF NOT EXISTS idx_analysis_history_user_date
    ON analysis_history_index(storage_root, scope_user_id, analysis_date DESC, stock_code DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_analysis_history_code_date
    ON analysis_history_index(storage_root, stock_code, scope_user_id, analysis_date DESC)
    """,
)

INDUSTRY_CHAIN_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS industry_chain_history_index (
    storage_root  TEXT    NOT NULL,
    scope_user_id INTEGER NOT NULL DEFAULT 0,
    safe_name     TEXT    NOT NULL,
    name          TEXT    NOT NULL,
    archive_id    TEXT    NOT NULL,
    saved_at      TEXT    NOT NULL DEFAULT '',
    title         TEXT    NOT NULL DEFAULT '',
    summary       TEXT    NOT NULL DEFAULT '',
    file_path     TEXT    NOT NULL,
    PRIMARY KEY (storage_root, scope_user_id, safe_name, archive_id)
)
"""
INDUSTRY_CHAIN_HISTORY_INDEXES = (
    """
    CREATE INDEX IF NOT EXISTS idx_industry_history_user_archive
    ON industry_chain_history_index(storage_root, scope_user_id, archive_id DESC, safe_name DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_industry_history_name_archive
    ON industry_chain_history_index(storage_root, safe_name, scope_user_id, archive_id DESC)
    """,
)

MARKET_TABLES.extend(
    [
        HISTORY_INDEX_STATE_TABLE,
        ANALYSIS_HISTORY_TABLE,
        *ANALYSIS_HISTORY_INDEXES,
        INDUSTRY_CHAIN_HISTORY_TABLE,
        *INDUSTRY_CHAIN_HISTORY_INDEXES,
    ]
)
