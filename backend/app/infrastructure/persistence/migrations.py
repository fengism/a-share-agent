import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from app.infrastructure.persistence.connection import unit_of_work

logger = logging.getLogger(__name__)

MIGRATION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    applied_at TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
)
"""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


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


USER_MIGRATIONS = (
    Migration(1, "add users.must_change_password", _add_must_change_password),
    Migration(2, "add authentication lookup indexes", _add_auth_indexes),
    Migration(3, "add bot command jobs", _add_bot_command_jobs),
    Migration(4, "add bot rate limit events", _add_bot_rate_limit_events),
    Migration(5, "add bot job lookup fields", _add_bot_job_lookup_fields),
    Migration(6, "add user config key index", _add_user_config_key_index),
    Migration(7, "add quant research", _add_quant_backtest_runs),
)

MARKET_MIGRATIONS = (
    Migration(3, "add background task leases", _add_background_task_leases),
    Migration(4, "add twitter post fields and indexes", _add_twitter_post_fields_and_indexes),
    Migration(5, "add twitter refresh state", _add_twitter_refresh_state),
    Migration(6, "add twitter retention index", _add_twitter_retention_index),
    Migration(7, "add twitter analysis cache", _add_twitter_analysis_cache),
    Migration(8, "add twitter analysis snapshots", _add_twitter_analysis_snapshots),
    Migration(9, "finalize twitter analysis snapshots", _finalize_twitter_analysis_snapshots),
)


def apply_migrations(
    conn: sqlite3.Connection,
    migrations: tuple[Migration, ...],
) -> None:
    """按版本顺序事务化执行尚未应用的 SQLite 迁移。"""
    conn.execute(MIGRATION_TABLE)
    conn.commit()
    applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    for migration in migrations:
        if migration.version in applied:
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
                "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
                (migration.version, migration.name),
            )
        logger.info("数据库迁移完成: version=%s name=%s", migration.version, migration.name)
