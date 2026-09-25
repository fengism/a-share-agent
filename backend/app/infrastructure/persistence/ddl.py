"""所有表的 DDL 定义。新增数据类型只需追加建表语句。"""

WORKFLOW_JOB_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS workflow_jobs (
        id           TEXT PRIMARY KEY,
        kind         TEXT NOT NULL CHECK (kind IN ('analysis', 'industry_chain', 'screener_strategy', 'daily_review')),
        user_id      INTEGER NOT NULL,
        dedupe_key   TEXT NOT NULL,
        request_json TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')),
        attempts     INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 2,
        available_at REAL NOT NULL,
        lease_owner  TEXT,
        lease_until  REAL,
        last_error   TEXT,
        created_at   REAL NOT NULL,
        updated_at   REAL NOT NULL,
        completed_at REAL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_jobs_active_key
    ON workflow_jobs(kind, user_id, dedupe_key)
    WHERE status IN ('pending', 'running')
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_workflow_jobs_claim
    ON workflow_jobs(status, available_at, lease_until, created_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS workflow_job_events (
        job_id       TEXT NOT NULL,
        attempt      INTEGER NOT NULL,
        sequence     INTEGER NOT NULL,
        event_type   TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at   REAL NOT NULL,
        PRIMARY KEY (job_id, attempt, sequence),
        FOREIGN KEY (job_id) REFERENCES workflow_jobs(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_workflow_job_events_read
    ON workflow_job_events(job_id, attempt, sequence)
    """,
)

WORKFLOW_ACTIVE_USER_INDEX = """
CREATE INDEX IF NOT EXISTS idx_workflow_jobs_active_user
ON workflow_jobs(user_id)
WHERE status IN ('pending', 'running')
"""

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

MARKET_TABLES.extend(
    [
        """
        CREATE TABLE IF NOT EXISTS background_task_leases (
            task_name   TEXT PRIMARY KEY,
            owner_id    TEXT NOT NULL,
            lease_until REAL NOT NULL,
            updated_at  REAL NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS twitter_feed_refresh_state (
            author            TEXT PRIMARY KEY,
            last_refreshed_at REAL NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_twitter_posts_author_fetched
        ON twitter_posts(author, fetched_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_twitter_posts_author_published
        ON twitter_posts(author, publish_time DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_twitter_posts_fetched_at
        ON twitter_posts(fetched_at)
        """,
    ]
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

MARKET_TABLES.extend(
    [
        """
        CREATE INDEX IF NOT EXISTS idx_twitter_analysis_snapshots_user_time
        ON twitter_analysis_snapshots(username, generated_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_twitter_analysis_snapshots_generated_at
        ON twitter_analysis_snapshots(generated_at)
        """,
    ]
)

# ── 账号系统：用户 / 会话 / 邀请 / 每用户私密配置 ──
USER_TABLES = []

USER_TABLES.append(
    """
    CREATE TABLE IF NOT EXISTS users (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        username             TEXT    NOT NULL UNIQUE COLLATE NOCASE,
        password_hash        TEXT    NOT NULL,
        is_admin             INTEGER NOT NULL DEFAULT 0,
        is_active            INTEGER NOT NULL DEFAULT 1,
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

USER_TABLES.extend(
    [
        "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry ON auth_sessions(expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_invites_creator_created ON invites(created_by, created_at DESC)",
        """
        CREATE TABLE IF NOT EXISTS bot_command_jobs (
            id              TEXT PRIMARY KEY,
            event_id        TEXT NOT NULL UNIQUE,
            platform        TEXT NOT NULL,
            request_user_id TEXT NOT NULL DEFAULT '',
            command_name    TEXT NOT NULL DEFAULT '',
            message_json    TEXT NOT NULL,
            response_json   TEXT,
            status          TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'running', 'succeeded', 'failed')),
            attempts        INTEGER NOT NULL DEFAULT 0,
            max_attempts    INTEGER NOT NULL DEFAULT 3,
            available_at    REAL NOT NULL,
            lease_owner     TEXT,
            lease_until     REAL,
            last_error      TEXT,
            created_at      REAL NOT NULL,
            updated_at      REAL NOT NULL,
            completed_at    REAL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_bot_command_jobs_claim
        ON bot_command_jobs(status, available_at, lease_until, created_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_bot_command_jobs_user_time
        ON bot_command_jobs(request_user_id, created_at DESC)
        """,
        """
        CREATE TABLE IF NOT EXISTS bot_rate_limit_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_key   TEXT NOT NULL,
            occurred_at REAL NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_bot_rate_limit_events_scope_time
        ON bot_rate_limit_events(scope_key, occurred_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_bot_rate_limit_events_time
        ON bot_rate_limit_events(occurred_at)
        """,
    ]
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
        "CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_resets(user_id)",
        """
        CREATE INDEX IF NOT EXISTS idx_password_resets_expiry_used
        ON password_resets(expires_at, used_at)
        """,
        "CREATE INDEX IF NOT EXISTS idx_user_config_key ON user_config(key)",
    ]
)

USER_TABLES.append(
    """
    CREATE TABLE IF NOT EXISTS login_audit_logs (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        username   TEXT    NOT NULL,
        user_id    INTEGER,
        ip_address TEXT    NOT NULL DEFAULT '',
        user_agent TEXT    NOT NULL DEFAULT '',
        status     TEXT    NOT NULL,
        details    TEXT    NOT NULL DEFAULT '',
        created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """
)

USER_TABLES.extend(
    [
        "CREATE INDEX IF NOT EXISTS idx_login_audit_created ON login_audit_logs(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_login_audit_username ON login_audit_logs(username, created_at DESC)",
    ]
)

PORTFOLIO_TRANSACTION_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS portfolio_transactions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        stock_code  TEXT    NOT NULL,
        stock_name  TEXT    NOT NULL DEFAULT '',
        side        TEXT    NOT NULL CHECK (side IN ('buy', 'sell')),
        trade_price REAL    NOT NULL CHECK (trade_price > 0),
        trade_time  TEXT    NOT NULL,
        shares      INTEGER NOT NULL CHECK (shares > 0),
        fee         REAL    NOT NULL DEFAULT 0 CHECK (fee >= 0),
        note        TEXT    NOT NULL DEFAULT '',
        created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_portfolio_transactions_user_time
    ON portfolio_transactions(user_id, trade_time DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_portfolio_transactions_user_stock_time
    ON portfolio_transactions(user_id, stock_code, trade_time, id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_portfolio_transactions_user_stock_id
    ON portfolio_transactions(user_id, stock_code, id DESC)
    """,
)

USER_TABLES.extend(PORTFOLIO_TRANSACTION_STATEMENTS)

PORTFOLIO_ACCOUNT_SETTINGS_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS portfolio_account_settings (
        user_id                  INTEGER PRIMARY KEY,
        initial_cash             REAL CHECK (initial_cash IS NULL OR initial_cash >= 0),
        max_total_position_pct   REAL NOT NULL DEFAULT 80
                                 CHECK (max_total_position_pct > 0 AND max_total_position_pct <= 100),
        max_single_stock_pct     REAL NOT NULL DEFAULT 30
                                 CHECK (max_single_stock_pct > 0 AND max_single_stock_pct <= 100),
        max_sector_pct           REAL NOT NULL DEFAULT 40
                                 CHECK (max_sector_pct > 0 AND max_sector_pct <= 100),
        updated_at               TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
)

USER_TABLES.extend(PORTFOLIO_ACCOUNT_SETTINGS_STATEMENTS)

WATCHLIST_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS watchlist_items (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        stock_code TEXT    NOT NULL,
        stock_name TEXT    NOT NULL DEFAULT '',
        note       TEXT    NOT NULL DEFAULT '',
        created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        UNIQUE(user_id, stock_code),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_watchlist_items_user_time
    ON watchlist_items(user_id, created_at DESC, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS watchlist_alerts (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id           INTEGER NOT NULL,
        stock_code        TEXT    NOT NULL,
        condition         TEXT    NOT NULL CHECK (
            condition IN ('price_above', 'price_below', 'change_pct_above', 'change_pct_below')
        ),
        threshold         REAL    NOT NULL,
        enabled           INTEGER NOT NULL DEFAULT 1,
        last_triggered_at TEXT,
        created_at        TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (user_id, stock_code)
            REFERENCES watchlist_items(user_id, stock_code) ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_watchlist_alerts_user_stock
    ON watchlist_alerts(user_id, stock_code, id)
    """,
)

USER_TABLES.extend(WATCHLIST_STATEMENTS)

CHAT_STATE_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS chat_states (
        user_id      INTEGER PRIMARY KEY,
        payload_json TEXT NOT NULL,
        updated_at   REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
)

CHAT_STATE_LATEST_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS chat_states (
        user_id      INTEGER PRIMARY KEY,
        payload_json TEXT NOT NULL,
        payload_hash TEXT NOT NULL DEFAULT '',
        revision     INTEGER NOT NULL DEFAULT 0,
        updated_at   REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
)

USER_TABLES.extend(CHAT_STATE_LATEST_STATEMENTS)

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

QUANT_STRATEGY_DRAFT_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS quant_strategy_drafts (
        id                TEXT PRIMARY KEY,
        created_by        INTEGER NOT NULL,
        prompt            TEXT NOT NULL,
        definition_json   TEXT NOT NULL,
        definition_hash   TEXT NOT NULL,
        status            TEXT NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft', 'validated', 'testing', 'backtested', 'published')),
        validation_json   TEXT,
        backtest_run_id   TEXT,
        quality_gate_json TEXT,
        published_path    TEXT,
        last_error        TEXT,
        created_at        REAL NOT NULL,
        updated_at        REAL NOT NULL,
        published_at      REAL,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (backtest_run_id) REFERENCES quant_backtest_runs(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_quant_strategy_drafts_updated
    ON quant_strategy_drafts(updated_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_quant_strategy_drafts_status
    ON quant_strategy_drafts(status, updated_at DESC)
    """,
)

USER_TABLES.extend(QUANT_STRATEGY_DRAFT_STATEMENTS)

QUANT_ACTIVE_USER_INDEX = """
CREATE INDEX IF NOT EXISTS idx_quant_backtest_runs_active_user
ON quant_backtest_runs(user_id)
WHERE status IN ('pending', 'running')
"""

WORKFLOW_RETENTION_INDEX = """
CREATE INDEX IF NOT EXISTS idx_workflow_jobs_retention
ON workflow_jobs(status, completed_at)
"""

USER_TABLES.extend(
    [
        QUANT_ACTIVE_USER_INDEX,
        *WORKFLOW_JOB_STATEMENTS,
        WORKFLOW_RETENTION_INDEX,
        WORKFLOW_ACTIVE_USER_INDEX,
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

# ── 申万行业基础数据（独立 industry_data.db） ──
INDUSTRY_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS sw_industry_classifications (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        market_group         TEXT NOT NULL CHECK (market_group IN ('A', 'HK', 'OVERSEAS')),
        exchange_suffix      TEXT NOT NULL,
        stock_code           TEXT NOT NULL UNIQUE,
        stock_name           TEXT NOT NULL DEFAULT '',
        sw_level1_name       TEXT NOT NULL DEFAULT '',
        sw_level2_name       TEXT NOT NULL DEFAULT '',
        sw_level3_name       TEXT NOT NULL DEFAULT '',
        sw_industry_code     TEXT NOT NULL DEFAULT '',
        source               TEXT NOT NULL DEFAULT 'manual',
        source_version       TEXT NOT NULL DEFAULT '',
        effective_date       TEXT,
        is_manual_override   INTEGER NOT NULL DEFAULT 0 CHECK (is_manual_override IN (0, 1)),
        created_at           TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at           TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sw_industry_market ON sw_industry_classifications(market_group)",
    "CREATE INDEX IF NOT EXISTS idx_sw_industry_exchange ON sw_industry_classifications(exchange_suffix)",
    "CREATE INDEX IF NOT EXISTS idx_sw_industry_stock_name ON sw_industry_classifications(stock_name)",
    "CREATE INDEX IF NOT EXISTS idx_sw_industry_level1 ON sw_industry_classifications(sw_level1_name)",
    "CREATE INDEX IF NOT EXISTS idx_sw_industry_level2 ON sw_industry_classifications(sw_level2_name)",
    "CREATE INDEX IF NOT EXISTS idx_sw_industry_level3 ON sw_industry_classifications(sw_level3_name)",
    "CREATE INDEX IF NOT EXISTS idx_sw_industry_code ON sw_industry_classifications(sw_industry_code)",
    "CREATE INDEX IF NOT EXISTS idx_sw_industry_updated ON sw_industry_classifications(updated_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS sw_industry_refresh_state (
        provider             TEXT PRIMARY KEY,
        enabled              INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        interval_seconds     INTEGER NOT NULL DEFAULT 86400,
        last_started_at      TEXT,
        last_succeeded_at    TEXT,
        last_failed_at       TEXT,
        last_error           TEXT,
        last_added           INTEGER NOT NULL DEFAULT 0,
        last_updated         INTEGER NOT NULL DEFAULT 0,
        last_unchanged       INTEGER NOT NULL DEFAULT 0,
        updated_at           TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sw_industry_import_batches (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        import_token         TEXT NOT NULL UNIQUE,
        content_hash         TEXT NOT NULL,
        filename             TEXT NOT NULL,
        source_version       TEXT NOT NULL DEFAULT '',
        effective_date       TEXT,
        status               TEXT NOT NULL CHECK (status IN ('previewed', 'committed', 'failed')),
        total_rows           INTEGER NOT NULL DEFAULT 0,
        valid_rows           INTEGER NOT NULL DEFAULT 0,
        added_rows           INTEGER NOT NULL DEFAULT 0,
        updated_rows         INTEGER NOT NULL DEFAULT 0,
        unchanged_rows       INTEGER NOT NULL DEFAULT 0,
        skipped_rows         INTEGER NOT NULL DEFAULT 0,
        conflict_rows        INTEGER NOT NULL DEFAULT 0,
        invalid_rows         INTEGER NOT NULL DEFAULT 0,
        warnings_json        TEXT NOT NULL DEFAULT '[]',
        created_at           TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        committed_at         TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sw_import_hash ON sw_industry_import_batches(content_hash)",
    "CREATE INDEX IF NOT EXISTS idx_sw_import_created ON sw_industry_import_batches(created_at DESC)",
    # ── 个股概念数据 ──
    """
    CREATE TABLE IF NOT EXISTS stock_concepts (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        name                 TEXT NOT NULL UNIQUE,
        stock_count          INTEGER NOT NULL DEFAULT 0,
        created_at           TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at           TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_stock_concepts_name ON stock_concepts(name)",
    """
    CREATE TABLE IF NOT EXISTS stock_concept_mappings (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        market_group         TEXT NOT NULL DEFAULT 'A' CHECK (market_group IN ('A', 'HK', 'OVERSEAS')),
        exchange_suffix      TEXT NOT NULL DEFAULT 'SZ',
        stock_code           TEXT NOT NULL,
        stock_name           TEXT NOT NULL DEFAULT '',
        concepts_json        TEXT NOT NULL DEFAULT '[]',
        source               TEXT NOT NULL DEFAULT 'manual',
        source_version       TEXT NOT NULL DEFAULT '',
        is_manual_override   INTEGER NOT NULL DEFAULT 0 CHECK (is_manual_override IN (0, 1)),
        created_at           TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at           TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        UNIQUE(stock_code)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_concept_map_stock_code ON stock_concept_mappings(stock_code)",
    "CREATE INDEX IF NOT EXISTS idx_concept_map_stock_name ON stock_concept_mappings(stock_name)",
    "CREATE INDEX IF NOT EXISTS idx_concept_map_market ON stock_concept_mappings(market_group)",
    """
    CREATE TABLE IF NOT EXISTS stock_concept_import_batches (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        import_token         TEXT NOT NULL UNIQUE,
        content_hash         TEXT NOT NULL,
        filename             TEXT NOT NULL,
        source_version       TEXT NOT NULL DEFAULT '',
        status               TEXT NOT NULL CHECK (status IN ('previewed', 'committed', 'failed')),
        total_rows           INTEGER NOT NULL DEFAULT 0,
        valid_rows           INTEGER NOT NULL DEFAULT 0,
        added_rows           INTEGER NOT NULL DEFAULT 0,
        updated_rows         INTEGER NOT NULL DEFAULT 0,
        unchanged_rows       INTEGER NOT NULL DEFAULT 0,
        skipped_rows         INTEGER NOT NULL DEFAULT 0,
        invalid_rows         INTEGER NOT NULL DEFAULT 0,
        warnings_json        TEXT NOT NULL DEFAULT '[]',
        created_at           TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        committed_at         TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_concept_import_hash ON stock_concept_import_batches(content_hash)",
    "CREATE INDEX IF NOT EXISTS idx_concept_import_created ON stock_concept_import_batches(created_at DESC)",
    # ── 个股基础资料库 ──
    """
    CREATE TABLE IF NOT EXISTS stock_basic_profiles (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        market_group         TEXT NOT NULL DEFAULT 'A' CHECK (market_group IN ('A', 'HK', 'OVERSEAS')),
        exchange             TEXT NOT NULL DEFAULT '',
        board                TEXT NOT NULL DEFAULT '',
        stock_code           TEXT NOT NULL UNIQUE,
        stock_name           TEXT NOT NULL DEFAULT '',
        listing_date         TEXT,
        main_business        TEXT NOT NULL DEFAULT '',
        business_scope       TEXT NOT NULL DEFAULT '',
        products             TEXT NOT NULL DEFAULT '',
        industry             TEXT NOT NULL DEFAULT '',
        sw_level1_name       TEXT NOT NULL DEFAULT '',
        sw_level2_name       TEXT NOT NULL DEFAULT '',
        sw_level3_name       TEXT NOT NULL DEFAULT '',
        city                 TEXT NOT NULL DEFAULT '',
        province             TEXT NOT NULL DEFAULT '',
        legal_repr           TEXT NOT NULL DEFAULT '',
        registered_capital   TEXT NOT NULL DEFAULT '',
        setup_date           TEXT,
        website              TEXT NOT NULL DEFAULT '',
        company_intro        TEXT NOT NULL DEFAULT '',
        source               TEXT NOT NULL DEFAULT 'exchange',
        source_version       TEXT NOT NULL DEFAULT '',
        is_manual_override   INTEGER NOT NULL DEFAULT 0 CHECK (is_manual_override IN (0, 1)),
        created_at           TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at           TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_stock_basic_profiles_market ON stock_basic_profiles(market_group)",
    "CREATE INDEX IF NOT EXISTS idx_stock_basic_profiles_exchange ON stock_basic_profiles(exchange)",
    "CREATE INDEX IF NOT EXISTS idx_stock_basic_profiles_board ON stock_basic_profiles(board)",
    "CREATE INDEX IF NOT EXISTS idx_stock_basic_profiles_code ON stock_basic_profiles(stock_code)",
    "CREATE INDEX IF NOT EXISTS idx_stock_basic_profiles_name ON stock_basic_profiles(stock_name)",
    "CREATE INDEX IF NOT EXISTS idx_stock_basic_profiles_listing_date ON stock_basic_profiles(listing_date)",
    "CREATE INDEX IF NOT EXISTS idx_stock_basic_profiles_updated ON stock_basic_profiles(updated_at DESC)",
]


# ── 国家队 ETF 份额（market_data.db） ──
NATIONAL_TEAM_ETF_SHARES_TABLE = """
CREATE TABLE IF NOT EXISTS national_team_etf_shares (
    code       TEXT    NOT NULL,
    date       TEXT    NOT NULL,
    shares     REAL    NOT NULL,
    updated_at REAL    NOT NULL,
    source TEXT NOT NULL DEFAULT 'unknown',
    verification_status TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (code, date)
)
"""
NATIONAL_TEAM_ETF_SHARES_INDEX = """
CREATE INDEX IF NOT EXISTS idx_national_team_etf_shares_code_date
ON national_team_etf_shares(code, date DESC)
"""
NATIONAL_TEAM_ETF_BACKFILL_TABLE = """
CREATE TABLE IF NOT EXISTS national_team_etf_backfill_state (
    scope      TEXT    NOT NULL,
    date       TEXT    NOT NULL,
    updated_at REAL    NOT NULL,
    PRIMARY KEY (scope, date)
)
"""

NATIONAL_TEAM_ETF_OBSERVATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS national_team_etf_observations (
    code TEXT NOT NULL,
    source TEXT NOT NULL,
    shares REAL NOT NULL,
    business_date TEXT,
    fetched_at REAL NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'provisional',
    PRIMARY KEY (code, source)
)
"""
NATIONAL_TEAM_ETF_IMPORTS_TABLE = """
CREATE TABLE IF NOT EXISTS national_team_etf_imports (
    path TEXT PRIMARY KEY,
    imported_at REAL NOT NULL
)
"""

MARKET_TABLES.extend(
    [
        NATIONAL_TEAM_ETF_SHARES_TABLE,
        NATIONAL_TEAM_ETF_SHARES_INDEX,
        NATIONAL_TEAM_ETF_BACKFILL_TABLE,
        NATIONAL_TEAM_ETF_OBSERVATIONS_TABLE,
        NATIONAL_TEAM_ETF_IMPORTS_TABLE,
    ]
)


# ── 板块成分股历史快照（market_data.db） ──
MARKET_TABLES.extend(
    [
        """
        CREATE TABLE IF NOT EXISTS sector_constituent_snapshots (
            source           TEXT NOT NULL,
            plate_id         TEXT NOT NULL,
            constituent_date TEXT NOT NULL,
            fetched_at       TEXT NOT NULL,
            stock_count      INTEGER NOT NULL,
            PRIMARY KEY (source, plate_id, constituent_date)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sector_constituents (
            source           TEXT NOT NULL,
            plate_id         TEXT NOT NULL,
            constituent_date TEXT NOT NULL,
            stock_code       TEXT NOT NULL,
            stock_name       TEXT NOT NULL DEFAULT '',
            tags             TEXT NOT NULL DEFAULT '',
            position         INTEGER NOT NULL,
            history_json     TEXT NOT NULL,
            PRIMARY KEY (source, plate_id, constituent_date, stock_code),
            FOREIGN KEY (source, plate_id, constituent_date)
                REFERENCES sector_constituent_snapshots(source, plate_id, constituent_date)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sector_constituent_snapshot_lookup
        ON sector_constituent_snapshots(source, plate_id, constituent_date DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sector_constituent_stock_lookup
        ON sector_constituents(stock_code, constituent_date DESC)
        """,
    ]
)
