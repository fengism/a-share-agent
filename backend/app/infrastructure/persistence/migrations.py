import hashlib
import inspect
import logging
import sqlite3
import textwrap
from collections.abc import Callable
from dataclasses import dataclass

from app.infrastructure.persistence.connection import unit_of_work
from app.infrastructure.persistence.ddl import (
    PORTFOLIO_ACCOUNT_SETTINGS_STATEMENTS,
    PORTFOLIO_TRANSACTION_STATEMENTS,
    QUANT_ACTIVE_USER_INDEX,
    QUANT_STRATEGY_DRAFT_STATEMENTS,
    WORKFLOW_ACTIVE_USER_INDEX,
    WORKFLOW_JOB_STATEMENTS,
)

logger = logging.getLogger(__name__)

MIGRATION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    checksum   TEXT,
    applied_at TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
)
"""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]

    @property
    def checksum(self) -> str:
        source = textwrap.dedent(inspect.getsource(self.apply)).strip()
        payload = f"{self.version}\n{self.name}\n{source}".encode()
        return hashlib.sha256(payload).hexdigest()


def _add_must_change_password(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if columns and "must_change_password" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")


def _add_auth_indexes(conn: sqlite3.Connection) -> None:
    statements = (
        "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry ON auth_sessions(expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_invites_creator_created ON invites(created_by, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_resets(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_password_resets_expiry_used ON password_resets(expires_at, used_at)",
    )
    for statement in statements:
        conn.execute(statement)


def _add_background_task_leases(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS background_task_leases (
            task_name   TEXT PRIMARY KEY,
            owner_id    TEXT NOT NULL,
            lease_until REAL NOT NULL,
            updated_at  REAL NOT NULL
        )
        """
    )


def _add_twitter_post_fields_and_indexes(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(twitter_posts)").fetchall()}
    if columns and "image_url" not in columns:
        conn.execute("ALTER TABLE twitter_posts ADD COLUMN image_url TEXT NOT NULL DEFAULT ''")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_twitter_posts_author_fetched ON twitter_posts(author, fetched_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_twitter_posts_author_published ON twitter_posts(author, publish_time DESC)"
    )


def _add_twitter_refresh_state(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS twitter_feed_refresh_state (
            author            TEXT PRIMARY KEY,
            last_refreshed_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO twitter_feed_refresh_state(author, last_refreshed_at)
        SELECT author, COALESCE(CAST(strftime('%s', MAX(fetched_at)) AS REAL), 0)
        FROM twitter_posts
        WHERE author <> ''
        GROUP BY author
        ON CONFLICT(author) DO NOTHING
        """
    )


def _add_twitter_retention_index(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_twitter_posts_fetched_at ON twitter_posts(fetched_at)")


def _add_twitter_analysis_cache(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS twitter_analysis_cache (
            username     TEXT PRIMARY KEY,
            source_hash  TEXT NOT NULL,
            result_json  TEXT NOT NULL,
            generated_at REAL NOT NULL
        )
        """
    )


def _add_twitter_analysis_snapshots(conn: sqlite3.Connection) -> None:
    conn.execute(
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
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_twitter_analysis_snapshots_user_time
        ON twitter_analysis_snapshots(username, generated_at DESC)
        """
    )


def _finalize_twitter_analysis_snapshots(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS twitter_analysis_cache")
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_twitter_analysis_snapshots_generated_at
        ON twitter_analysis_snapshots(generated_at)
        """
    )


def _add_user_config_key_index(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_config_key ON user_config(key)")


def _add_bot_command_jobs(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_command_jobs (
            id             TEXT PRIMARY KEY,
            event_id       TEXT NOT NULL UNIQUE,
            platform       TEXT NOT NULL,
            request_user_id TEXT NOT NULL DEFAULT '',
            command_name   TEXT NOT NULL DEFAULT '',
            message_json   TEXT NOT NULL,
            response_json  TEXT,
            status         TEXT NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'running', 'succeeded', 'failed')),
            attempts       INTEGER NOT NULL DEFAULT 0,
            max_attempts   INTEGER NOT NULL DEFAULT 3,
            available_at   REAL NOT NULL,
            lease_owner    TEXT,
            lease_until    REAL,
            last_error     TEXT,
            created_at     REAL NOT NULL,
            updated_at     REAL NOT NULL,
            completed_at   REAL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bot_command_jobs_claim
        ON bot_command_jobs(status, available_at, lease_until, created_at)
        """
    )


def _add_bot_rate_limit_events(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_rate_limit_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_key   TEXT NOT NULL,
            occurred_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bot_rate_limit_events_scope_time
        ON bot_rate_limit_events(scope_key, occurred_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bot_rate_limit_events_time
        ON bot_rate_limit_events(occurred_at)
        """
    )


def _add_bot_job_lookup_fields(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(bot_command_jobs)").fetchall()}
    if "request_user_id" not in columns:
        conn.execute("ALTER TABLE bot_command_jobs ADD COLUMN request_user_id TEXT NOT NULL DEFAULT ''")
    if "command_name" not in columns:
        conn.execute("ALTER TABLE bot_command_jobs ADD COLUMN command_name TEXT NOT NULL DEFAULT ''")
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bot_command_jobs_claim
        ON bot_command_jobs(status, available_at, lease_until, created_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bot_command_jobs_user_time
        ON bot_command_jobs(request_user_id, created_at DESC)
        """
    )


def _add_quant_backtest_runs(conn: sqlite3.Connection) -> None:
    conn.execute(
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
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_quant_strategies_user_time
        ON quant_strategies(user_id, updated_at DESC)
        """
    )
    conn.execute(
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
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_quant_backtest_runs_claim
        ON quant_backtest_runs(status, available_at, lease_until, created_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_quant_backtest_runs_user_time
        ON quant_backtest_runs(user_id, created_at DESC)
        """
    )


def _add_workflow_jobs(conn: sqlite3.Connection) -> None:
    for statement in WORKFLOW_JOB_STATEMENTS:
        conn.execute(statement)


def _add_workflow_retention_index(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workflow_jobs_retention
        ON workflow_jobs(status, completed_at)
        """
    )


def _add_portfolio_transactions(conn: sqlite3.Connection) -> None:
    for statement in PORTFOLIO_TRANSACTION_STATEMENTS:
        conn.execute(statement)
    legacy_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'portfolio_positions'"
    ).fetchone()
    if legacy_table is None:
        return
    conn.execute(
        """
        INSERT INTO portfolio_transactions(
            id, user_id, stock_code, stock_name, side, trade_price,
            trade_time, shares, fee, note, created_at
        )
        SELECT id, user_id, stock_code, stock_name, 'buy', buy_price,
               buy_time, shares, 0, '', created_at
        FROM portfolio_positions
        WHERE NOT EXISTS (
            SELECT 1
            FROM portfolio_transactions AS transaction_record
            WHERE transaction_record.id = portfolio_positions.id
        )
        ORDER BY id
        """
    )


def _add_portfolio_account_settings(conn: sqlite3.Connection) -> None:
    for statement in PORTFOLIO_ACCOUNT_SETTINGS_STATEMENTS:
        conn.execute(statement)


def _remove_legacy_portfolio_positions(conn: sqlite3.Connection) -> None:
    legacy_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'portfolio_positions'"
    ).fetchone()
    if legacy_table is None:
        return
    backfill_applied = conn.execute("SELECT 1 FROM schema_migrations WHERE version = 10").fetchone()
    if backfill_applied is None:
        raise RuntimeError("旧持仓清理前未完成交易流水回填")
    conn.execute("DROP INDEX IF EXISTS idx_portfolio_positions_user_time")
    conn.execute("DROP TABLE portfolio_positions")


def _add_watchlist(conn: sqlite3.Connection) -> None:
    from app.infrastructure.persistence.ddl import WATCHLIST_STATEMENTS

    for statement in WATCHLIST_STATEMENTS:
        conn.execute(statement)


def _add_chat_state(conn: sqlite3.Connection) -> None:
    from app.infrastructure.persistence.ddl import CHAT_STATE_STATEMENTS

    for statement in CHAT_STATE_STATEMENTS:
        conn.execute(statement)


def _add_chat_state_payload_hash(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(chat_states)").fetchall()}
    if "payload_hash" not in columns:
        conn.execute("ALTER TABLE chat_states ADD COLUMN payload_hash TEXT NOT NULL DEFAULT ''")
    rows = conn.execute(
        "SELECT user_id, payload_json FROM chat_states WHERE payload_hash = ''"
    ).fetchall()
    conn.executemany(
        "UPDATE chat_states SET payload_hash = ? WHERE user_id = ?",
        [
            (hashlib.sha256(str(row[1]).encode("utf-8")).hexdigest(), int(row[0]))
            for row in rows
        ],
    )


def _add_chat_state_revision(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(chat_states)").fetchall()}
    if "revision" not in columns:
        conn.execute("ALTER TABLE chat_states ADD COLUMN revision INTEGER NOT NULL DEFAULT 0")


def _add_quant_strategy_drafts(conn: sqlite3.Connection) -> None:
    for statement in QUANT_STRATEGY_DRAFT_STATEMENTS:
        conn.execute(statement)


def _add_active_job_quota_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(WORKFLOW_ACTIVE_USER_INDEX)
    conn.execute(QUANT_ACTIVE_USER_INDEX)


def _add_screener_strategy_workflow_kind(conn: sqlite3.Connection) -> None:
    table = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'workflow_jobs'"
    ).fetchone()
    if table is None:
        for statement in WORKFLOW_JOB_STATEMENTS:
            conn.execute(statement)
        conn.execute(WORKFLOW_ACTIVE_USER_INDEX)
        _add_workflow_retention_index(conn)
        return
    if "screener_strategy" in str(table[0]):
        return

    has_events = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'workflow_job_events'"
    ).fetchone() is not None
    if has_events:
        conn.execute("ALTER TABLE workflow_job_events RENAME TO workflow_job_events_v17")
    conn.execute("ALTER TABLE workflow_jobs RENAME TO workflow_jobs_v17")
    for index_name in (
        "idx_workflow_jobs_active_key",
        "idx_workflow_jobs_claim",
        "idx_workflow_jobs_retention",
        "idx_workflow_jobs_active_user",
        "idx_workflow_job_events_read",
    ):
        conn.execute(f'DROP INDEX IF EXISTS "{index_name}"')

    for statement in WORKFLOW_JOB_STATEMENTS:
        conn.execute(statement)
    conn.execute(
        """
        INSERT INTO workflow_jobs(
            id, kind, user_id, dedupe_key, request_json, status,
            attempts, max_attempts, available_at, lease_owner, lease_until,
            last_error, created_at, updated_at, completed_at
        )
        SELECT
            id, kind, user_id, dedupe_key, request_json, status,
            attempts, max_attempts, available_at, lease_owner, lease_until,
            last_error, created_at, updated_at, completed_at
        FROM workflow_jobs_v17
        """
    )
    if has_events:
        conn.execute(
            """
            INSERT INTO workflow_job_events(
                job_id, attempt, sequence, event_type, payload_json, created_at
            )
            SELECT job_id, attempt, sequence, event_type, payload_json, created_at
            FROM workflow_job_events_v17
            """
        )
        conn.execute("DROP TABLE workflow_job_events_v17")
    conn.execute("DROP TABLE workflow_jobs_v17")
    conn.execute(WORKFLOW_ACTIVE_USER_INDEX)
    _add_workflow_retention_index(conn)


def _add_daily_review_workflow_kind(conn: sqlite3.Connection) -> None:
    table = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'workflow_jobs'"
    ).fetchone()
    if table is None:
        for statement in WORKFLOW_JOB_STATEMENTS:
            conn.execute(statement)
        conn.execute(WORKFLOW_ACTIVE_USER_INDEX)
        _add_workflow_retention_index(conn)
        return
    if "daily_review" in str(table[0]):
        return

    has_events = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'workflow_job_events'"
    ).fetchone() is not None
    if has_events:
        conn.execute("ALTER TABLE workflow_job_events RENAME TO workflow_job_events_v19")
    conn.execute("ALTER TABLE workflow_jobs RENAME TO workflow_jobs_v19")
    for index_name in (
        "idx_workflow_jobs_active_key",
        "idx_workflow_jobs_claim",
        "idx_workflow_jobs_retention",
        "idx_workflow_jobs_active_user",
        "idx_workflow_job_events_read",
    ):
        conn.execute(f'DROP INDEX IF EXISTS "{index_name}"')

    for statement in WORKFLOW_JOB_STATEMENTS:
        conn.execute(statement)
    conn.execute(
        """
        INSERT INTO workflow_jobs(
            id, kind, user_id, dedupe_key, request_json, status,
            attempts, max_attempts, available_at, lease_owner, lease_until,
            last_error, created_at, updated_at, completed_at
        )
        SELECT
            id, kind, user_id, dedupe_key, request_json, status,
            attempts, max_attempts, available_at, lease_owner, lease_until,
            last_error, created_at, updated_at, completed_at
        FROM workflow_jobs_v19
        """
    )
    if has_events:
        conn.execute(
            """
            INSERT INTO workflow_job_events(
                job_id, attempt, sequence, event_type, payload_json, created_at
            )
            SELECT job_id, attempt, sequence, event_type, payload_json, created_at
            FROM workflow_job_events_v19
            """
        )
        conn.execute("DROP TABLE workflow_job_events_v19")
    conn.execute("DROP TABLE workflow_jobs_v19")
    conn.execute(WORKFLOW_ACTIVE_USER_INDEX)
    _add_workflow_retention_index(conn)


def _add_users_is_active(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if columns and "is_active" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")


def _add_login_audit_logs(conn: sqlite3.Connection) -> None:
    conn.execute(
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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_login_audit_created ON login_audit_logs(created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_login_audit_username ON login_audit_logs(username, created_at DESC)"
    )


USER_MIGRATIONS = (
    Migration(1, "add users.must_change_password", _add_must_change_password),
    Migration(2, "add authentication lookup indexes", _add_auth_indexes),
    Migration(3, "add bot command jobs", _add_bot_command_jobs),
    Migration(4, "add bot rate limit events", _add_bot_rate_limit_events),
    Migration(5, "add bot job lookup fields", _add_bot_job_lookup_fields),
    Migration(6, "add user config key index", _add_user_config_key_index),
    Migration(7, "add quant research", _add_quant_backtest_runs),
    Migration(8, "add durable workflow jobs", _add_workflow_jobs),
    Migration(9, "add workflow retention index", _add_workflow_retention_index),
    Migration(10, "add portfolio transactions", _add_portfolio_transactions),
    Migration(11, "remove legacy portfolio positions", _remove_legacy_portfolio_positions),
    Migration(12, "add user watchlists and alerts", _add_watchlist),
    Migration(13, "add synchronized chat state", _add_chat_state),
    Migration(14, "add active job quota indexes", _add_active_job_quota_indexes),
    Migration(15, "add synchronized chat state payload hash", _add_chat_state_payload_hash),
    Migration(16, "add synchronized chat state revision", _add_chat_state_revision),
    Migration(17, "add quant strategy drafts", _add_quant_strategy_drafts),
    Migration(18, "add screener strategy workflow kind", _add_screener_strategy_workflow_kind),
    Migration(19, "add daily review workflow kind", _add_daily_review_workflow_kind),
    Migration(20, "add portfolio account settings", _add_portfolio_account_settings),
    Migration(21, "add users is_active", _add_users_is_active),
    Migration(22, "add login audit logs", _add_login_audit_logs),
)


def _add_national_team_etf_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS national_team_etf_shares (
            code       TEXT    NOT NULL,
            date       TEXT    NOT NULL,
            shares     REAL    NOT NULL,
            updated_at REAL    NOT NULL,
            PRIMARY KEY (code, date)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_national_team_etf_shares_code_date "
        "ON national_team_etf_shares(code, date DESC)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS national_team_etf_backfill_state (
            scope      TEXT    NOT NULL,
            date       TEXT    NOT NULL,
            updated_at REAL    NOT NULL,
            PRIMARY KEY (scope, date)
        )
        """
    )


def _add_sector_constituent_tables(conn: sqlite3.Connection) -> None:
    statements = (
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
    )
    for statement in statements:
        conn.execute(statement)


def _add_national_team_provenance(conn: sqlite3.Connection) -> None:
    from app.infrastructure.persistence.ddl import (
        NATIONAL_TEAM_ETF_IMPORTS_TABLE,
        NATIONAL_TEAM_ETF_OBSERVATIONS_TABLE,
    )

    columns = {row[1] for row in conn.execute("PRAGMA table_info(national_team_etf_shares)")}
    if "source" not in columns:
        conn.execute("ALTER TABLE national_team_etf_shares ADD COLUMN source TEXT NOT NULL DEFAULT 'unknown'")
    if "verification_status" not in columns:
        conn.execute("ALTER TABLE national_team_etf_shares ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'unknown'")
    conn.execute(NATIONAL_TEAM_ETF_OBSERVATIONS_TABLE)
    conn.execute(NATIONAL_TEAM_ETF_IMPORTS_TABLE)


MARKET_MIGRATIONS = (
    Migration(3, "add background task leases", _add_background_task_leases),
    Migration(4, "add twitter post fields and indexes", _add_twitter_post_fields_and_indexes),
    Migration(5, "add twitter refresh state", _add_twitter_refresh_state),
    Migration(6, "add twitter retention index", _add_twitter_retention_index),
    Migration(7, "add twitter analysis cache", _add_twitter_analysis_cache),
    Migration(8, "add twitter analysis snapshots", _add_twitter_analysis_snapshots),
    Migration(9, "finalize twitter analysis snapshots", _finalize_twitter_analysis_snapshots),
    Migration(10, "add national team etf tables", _add_national_team_etf_tables),
    Migration(11, "add sector constituent tables", _add_sector_constituent_tables),
    Migration(12, "add national team provenance", _add_national_team_provenance),
)

def _add_stock_concepts_tables(conn: sqlite3.Connection) -> None:
    statements = (
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
    )
    for statement in statements:
        conn.execute(statement)


def _add_stock_basic_profiles_tables(conn: sqlite3.Connection) -> None:
    statements = (
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
    )
    for statement in statements:
        conn.execute(statement)


def _normalize_hk_stock_codes(conn: sqlite3.Connection) -> None:
    """把 .HK 股票代码补齐到 5 位数字，统一港股代码口径。

    历史导入的港股代码存在 4 位（如 0700.HK）与 6 位（如 000700.HK）两种
    偏差，与 financial_data.hk 模块的 5 位口径对不上；已存在同码目标行时跳过。
    """
    for table in ("stock_concept_mappings", "sw_industry_classifications", "stock_basic_profiles"):
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        if exists is None:
            continue
        rows = conn.execute(
            f"SELECT id, stock_code FROM {table} WHERE stock_code LIKE '%.HK'"
        ).fetchall()
        for row_id, code in rows:
            base = str(code)[: -len(".HK")]
            if not base.isdigit() or len(base) >= 5:
                continue
            normalized = base.zfill(5) + ".HK"
            occupied = conn.execute(
                f"SELECT 1 FROM {table} WHERE stock_code = ? AND id <> ?",
                (normalized, row_id),
            ).fetchone()
            if occupied is not None:
                continue
            conn.execute(f"UPDATE {table} SET stock_code = ? WHERE id = ?", (normalized, row_id))


INDUSTRY_MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "add stock concepts tables", _add_stock_concepts_tables),
    Migration(2, "add stock basic profiles tables", _add_stock_basic_profiles_tables),
    Migration(3, "normalize hk stock codes to 5 digits", _normalize_hk_stock_codes),
)



def apply_migrations(
    conn: sqlite3.Connection,
    migrations: tuple[Migration, ...],
) -> None:
    """按版本顺序事务化执行尚未应用的 SQLite 迁移。"""
    conn.execute(MIGRATION_TABLE)
    migration_columns = {row[1] for row in conn.execute("PRAGMA table_info(schema_migrations)").fetchall()}
    if "checksum" not in migration_columns:
        conn.execute("ALTER TABLE schema_migrations ADD COLUMN checksum TEXT")
    conn.commit()
    applied = {
        int(row["version"]): row
        for row in conn.execute("SELECT version, name, checksum FROM schema_migrations").fetchall()
    }
    for migration in migrations:
        existing = applied.get(migration.version)
        if existing is not None:
            stored_checksum = existing["checksum"]
            if stored_checksum and stored_checksum != migration.checksum:
                raise RuntimeError(f"数据库迁移校验失败: version={migration.version} name={migration.name}")
            if not stored_checksum:
                conn.execute(
                    "UPDATE schema_migrations SET checksum = ? WHERE version = ?",
                    (migration.checksum, migration.version),
                )
                conn.commit()
            continue
        with unit_of_work(connection=conn, immediate=True) as work:
            already_applied = work.connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?",
                (migration.version,),
            ).fetchone()
            if already_applied is not None:
                continue
            migration.apply(work.connection)
            work.connection.execute(
                "INSERT INTO schema_migrations(version, name, checksum) VALUES (?, ?, ?)",
                (migration.version, migration.name, migration.checksum),
            )
        logger.info("数据库迁移完成: version=%s name=%s", migration.version, migration.name)
