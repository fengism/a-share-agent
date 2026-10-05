"""独立 SQLite 市场日行情库。

该库有意不复用 app.infrastructure.persistence.connection：单文件可直接复制迁移，
也不会把高体量日行情写入已有 market_data.db。
"""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import threading
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.modules.market_daily.models import (
    MarketCorporateAction,
    MarketDailyAdjustmentFactor,
    MarketDailyBar,
    MarketDailyBarPage,
    MarketDailyBarRecord,
    MarketDailyBarRefreshStatus,
    RefreshCheckpoint,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS market_daily_schema_migrations (
    version                 INTEGER PRIMARY KEY,
    name                    TEXT NOT NULL,
    checksum                TEXT NOT NULL,
    applied_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_daily_bars (
    market                  TEXT NOT NULL CHECK (market IN ('cn', 'hk')),
    instrument_type         TEXT NOT NULL CHECK (instrument_type IN ('stock', 'index')),
    code                    TEXT NOT NULL,
    name                    TEXT NOT NULL DEFAULT '',
    trade_date              TEXT NOT NULL,
    currency                TEXT NOT NULL CHECK (currency IN ('CNY', 'HKD')),
    open                    REAL,
    high                    REAL,
    low                     REAL,
    close                   REAL NOT NULL CHECK (close > 0),
    pre_close               REAL,
    change_amount           REAL,
    change_pct              REAL,
    volume                  REAL,
    amount                  REAL,
    turnover_pct            REAL,
    adjustment              TEXT NOT NULL DEFAULT 'none' CHECK (adjustment = 'none'),
    source                  TEXT NOT NULL,
    source_quote_time       TEXT,
    verification_status     TEXT NOT NULL CHECK (verification_status IN ('provisional', 'confirmed')),
    first_refreshed_at       TEXT NOT NULL,
    last_refreshed_at        TEXT NOT NULL,
    revision                INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    data_hash               TEXT NOT NULL,
    content_hash            TEXT,
    provenance_hash         TEXT,
    PRIMARY KEY (market, instrument_type, code, trade_date, adjustment)
);
CREATE INDEX IF NOT EXISTS idx_market_daily_bars_date_market
ON market_daily_bars(trade_date DESC, market, instrument_type, code);
CREATE INDEX IF NOT EXISTS idx_market_daily_bars_code_date
ON market_daily_bars(market, instrument_type, code, trade_date DESC);

CREATE TABLE IF NOT EXISTS market_daily_bar_observations (
    refresh_id              TEXT NOT NULL,
    checkpoint              TEXT NOT NULL CHECK (checkpoint IN ('initial', 'recheck')),
    refreshed_at             TEXT NOT NULL,
    market                  TEXT NOT NULL,
    instrument_type         TEXT NOT NULL,
    code                    TEXT NOT NULL,
    name                    TEXT NOT NULL DEFAULT '',
    trade_date              TEXT NOT NULL,
    currency                TEXT NOT NULL,
    open                    REAL,
    high                    REAL,
    low                     REAL,
    close                   REAL NOT NULL,
    pre_close               REAL,
    change_amount           REAL,
    change_pct              REAL,
    volume                  REAL,
    amount                  REAL,
    turnover_pct            REAL,
    adjustment              TEXT NOT NULL,
    source                  TEXT NOT NULL,
    source_quote_time       TEXT,
    data_hash               TEXT NOT NULL,
    content_hash            TEXT,
    provenance_hash         TEXT,
    PRIMARY KEY (refresh_id, market, instrument_type, code, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_market_daily_bar_observations_lookup
ON market_daily_bar_observations(market, instrument_type, code, trade_date DESC, refreshed_at DESC);

CREATE TABLE IF NOT EXISTS market_daily_bar_refresh_jobs (
    trade_date              TEXT NOT NULL,
    checkpoint              TEXT NOT NULL CHECK (checkpoint IN ('initial', 'recheck')),
    segment                 TEXT NOT NULL,
    status                  TEXT NOT NULL CHECK (status IN ('pending', 'running', 'success', 'skipped', 'failed')),
    attempts                INTEGER NOT NULL DEFAULT 0,
    next_retry_at           TEXT,
    expected_count          INTEGER,
    stored_count            INTEGER,
    last_error              TEXT,
    started_at              TEXT,
    completed_at            TEXT,
    attempt_id              TEXT,
    lease_expires_at        TEXT,
    worker_id               TEXT,
    updated_at              TEXT NOT NULL,
    PRIMARY KEY (trade_date, checkpoint, segment)
);
CREATE INDEX IF NOT EXISTS idx_market_daily_bar_refresh_jobs_history
ON market_daily_bar_refresh_jobs(status, trade_date DESC, checkpoint DESC, segment);
CREATE INDEX IF NOT EXISTS idx_market_daily_bar_refresh_jobs_retry
ON market_daily_bar_refresh_jobs(next_retry_at) WHERE status='failed';

CREATE TABLE IF NOT EXISTS market_daily_refresh_attempts (
    attempt_id              TEXT PRIMARY KEY,
    trade_date              TEXT NOT NULL,
    checkpoint              TEXT NOT NULL CHECK (checkpoint IN ('initial', 'recheck')),
    segment                 TEXT NOT NULL,
    attempt_no              INTEGER NOT NULL CHECK (attempt_no >= 1),
    worker_id               TEXT,
    status                  TEXT NOT NULL CHECK (status IN ('running', 'success', 'skipped', 'failed', 'superseded')),
    started_at              TEXT NOT NULL,
    completed_at            TEXT,
    next_retry_at           TEXT,
    error_message           TEXT
);
CREATE INDEX IF NOT EXISTS idx_market_daily_refresh_attempts_job
ON market_daily_refresh_attempts(trade_date DESC, checkpoint, segment, attempt_no DESC);

CREATE TABLE IF NOT EXISTS market_daily_refresh_runs (
    refresh_id              TEXT PRIMARY KEY,
    attempt_id              TEXT,
    trade_date              TEXT NOT NULL,
    checkpoint              TEXT NOT NULL CHECK (checkpoint IN ('initial', 'recheck')),
    segment                 TEXT NOT NULL,
    source                  TEXT NOT NULL,
    received_count          INTEGER NOT NULL CHECK (received_count >= 0),
    inserted_count          INTEGER NOT NULL CHECK (inserted_count >= 0),
    updated_count           INTEGER NOT NULL CHECK (updated_count >= 0),
    unchanged_count         INTEGER NOT NULL CHECK (unchanged_count >= 0),
    ignored_count           INTEGER NOT NULL CHECK (ignored_count >= 0),
    observation_count       INTEGER NOT NULL CHECK (observation_count >= 0),
    batch_hash              TEXT NOT NULL,
    refreshed_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_market_daily_refresh_runs_job
ON market_daily_refresh_runs(trade_date DESC, checkpoint, segment, refreshed_at DESC);

CREATE TABLE IF NOT EXISTS market_corporate_actions (
    market          TEXT NOT NULL CHECK (market IN ('cn', 'hk')),
    code            TEXT NOT NULL,
    action_date     TEXT NOT NULL,
    sequence        INTEGER NOT NULL CHECK (sequence >= 0),
    category        INTEGER NOT NULL,
    category_name   TEXT NOT NULL DEFAULT '',
    cash_dividend   REAL NOT NULL DEFAULT 0,
    rights_shares   REAL NOT NULL DEFAULT 0,
    rights_price    REAL NOT NULL DEFAULT 0,
    bonus_shares    REAL NOT NULL DEFAULT 0,
    split_ratio     REAL NOT NULL DEFAULT 0,
    raw_json        TEXT NOT NULL,
    source          TEXT NOT NULL,
    action_hash     TEXT NOT NULL,
    refreshed_at    TEXT NOT NULL,
    PRIMARY KEY (market, code, action_date, sequence)
);
CREATE INDEX IF NOT EXISTS idx_market_corporate_actions_code_date
ON market_corporate_actions(market, code, action_date DESC);

CREATE TABLE IF NOT EXISTS market_daily_adjustment_factors (
    market          TEXT NOT NULL CHECK (market IN ('cn', 'hk')),
    code            TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    qfq_multiplier  REAL NOT NULL,
    qfq_offset      REAL NOT NULL,
    hfq_multiplier  REAL,
    hfq_offset      REAL,
    action_hash     TEXT NOT NULL,
    algorithm_version TEXT NOT NULL,
    source          TEXT NOT NULL,
    calculated_at   TEXT NOT NULL,
    PRIMARY KEY (market, code, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_market_daily_adjustment_factors_code_date
ON market_daily_adjustment_factors(market, code, trade_date DESC);

CREATE TABLE IF NOT EXISTS market_adjustment_factor_state (
    market          TEXT NOT NULL CHECK (market IN ('cn', 'hk')),
    code            TEXT NOT NULL,
    action_hash     TEXT NOT NULL,
    algorithm_version TEXT NOT NULL,
    source          TEXT NOT NULL,
    calculated_at   TEXT NOT NULL,
    last_checked_at TEXT NOT NULL,
    last_error      TEXT,
    using_last_good INTEGER NOT NULL DEFAULT 0 CHECK (using_last_good IN (0, 1)),
    factor_count    INTEGER NOT NULL CHECK (factor_count >= 0),
    PRIMARY KEY (market, code)
);
"""


_MIGRATION_MANIFEST = {
    1: "baseline_schema",
}


def _migration_checksum(version: int, name: str) -> str:
    return hashlib.sha256(f"{version}:{name}".encode()).hexdigest()


def _record_migration_ledger(connection: sqlite3.Connection, current_version: int = 1) -> None:
    applied_at = _iso(_utc_now())
    for version, name in _MIGRATION_MANIFEST.items():
        if version > current_version:
            continue
        checksum = _migration_checksum(version, name)
        connection.execute(
            """
            INSERT OR REPLACE INTO market_daily_schema_migrations (
                version, name, checksum, applied_at
            ) VALUES (?, ?, ?, ?)
            """,
            (version, name, checksum, applied_at),
        )


def _encode_page_cursor(row: sqlite3.Row) -> str:
    payload = [
        row["trade_date"], row["market"], row["instrument_type"],
        row["code"], row["adjustment"],
    ]
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(encoded).decode().rstrip("=")


class InvalidMarketDailyCursorError(ValueError):
    """行情分页游标格式无效。"""


def _decode_page_cursor(value: str) -> tuple[str, str, str, str, str]:
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except Exception as error:
        raise InvalidMarketDailyCursorError("无效的市场日行情分页游标") from error
    if not isinstance(payload, list) or len(payload) != 5 or not all(
        isinstance(item, str) and item for item in payload
    ):
        raise InvalidMarketDailyCursorError("无效的市场日行情分页游标")
    trade_date, market, instrument_type, code, adjustment = payload
    try:
        date.fromisoformat(trade_date)
    except ValueError as error:
        raise InvalidMarketDailyCursorError("无效的市场日行情分页游标") from error
    if market not in {"cn", "hk"} or instrument_type not in {"stock", "index"}:
        raise InvalidMarketDailyCursorError("无效的市场日行情分页游标")
    return trade_date, market, instrument_type, code, adjustment


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds")


def _record_hash(record: MarketDailyBarRecord) -> str:
    payload = record.model_dump(mode="json", exclude={"source_quote_time"})
    payload["source_quote_time"] = _iso(record.source_quote_time)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _content_hash(record: MarketDailyBarRecord) -> str:
    """只包含会改变行情业务含义的字段，不含名称和来源元数据。"""
    payload = record.model_dump(
        mode="json", exclude={"name", "source", "source_quote_time"}
    )
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _provenance_hash(record: MarketDailyBarRecord) -> str:
    payload = {
        "name": record.name,
        "source": record.source,
        "source_quote_time": _iso(record.source_quote_time),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _row_to_price(row: sqlite3.Row) -> MarketDailyBar:
    return MarketDailyBar(
        market=row["market"],
        instrument_type=row["instrument_type"],
        code=row["code"],
        name=row["name"],
        trade_date=date.fromisoformat(row["trade_date"]),
        currency=row["currency"],
        open=row["open"],
        high=row["high"],
        low=row["low"],
        close=row["close"],
        pre_close=row["pre_close"],
        change_amount=row["change_amount"],
        change_pct=row["change_pct"],
        volume=row["volume"],
        amount=row["amount"],
        turnover_pct=row["turnover_pct"] if "turnover_pct" in row.keys() else None,
        adjustment=row["adjustment"],
        source=row["source"],
        source_quote_time=datetime.fromisoformat(row["source_quote_time"]) if row["source_quote_time"] else None,
        verification_status=row["verification_status"],
        revision=row["revision"],
        first_refreshed_at=datetime.fromisoformat(row["first_refreshed_at"]),
        last_refreshed_at=datetime.fromisoformat(row["last_refreshed_at"]),
    )


def _execute_schema(connection: sqlite3.Connection) -> None:
    for statement in _SCHEMA.split(";"):
        normalized = statement.strip()
        if normalized:
            connection.execute(normalized)


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _record_from_storage_row(row: sqlite3.Row) -> MarketDailyBarRecord:
    return MarketDailyBarRecord(
        market=row["market"],
        instrument_type=row["instrument_type"],
        code=row["code"],
        name=row["name"],
        trade_date=date.fromisoformat(row["trade_date"]),
        currency=row["currency"],
        open=row["open"],
        high=row["high"],
        low=row["low"],
        close=row["close"],
        pre_close=row["pre_close"],
        change_amount=row["change_amount"],
        change_pct=row["change_pct"],
        volume=row["volume"],
        amount=row["amount"],
        adjustment=row["adjustment"],
        source=row["source"],
        source_quote_time=(
            datetime.fromisoformat(row["source_quote_time"])
            if row["source_quote_time"] else None
        ),
    )


def _normalize_persisted_ohlc(connection: sqlite3.Connection) -> None:
    """修复旧快照中的停牌零值和不包含收盘价的高低价，并同步内容哈希。"""
    for table in ("market_daily_bars", "market_daily_bar_observations"):
        columns = _table_columns(connection, table)
        if not {"open", "high", "low", "close"}.issubset(columns):
            continue
        connection.execute(f"UPDATE {table} SET open=NULL WHERE open<=0")  # noqa: S608
        connection.execute(  # noqa: S608
            f"""
            UPDATE {table}
            SET high=MAX(close, COALESCE(NULLIF(open, 0), close)),
                low=MIN(close, COALESCE(NULLIF(open, 0), close))
            WHERE high IS NULL OR high<=0 OR low IS NULL OR low<=0
               OR high<MAX(close, COALESCE(NULLIF(open, 0), close))
               OR low>MIN(close, COALESCE(NULLIF(open, 0), close))
            """
        )
        rows = connection.execute(f"SELECT rowid AS _rowid, * FROM {table}").fetchall()  # noqa: S608
        if table == "market_daily_bars":
            connection.executemany(
                """
                UPDATE market_daily_bars SET data_hash=?
                WHERE market=? AND instrument_type=? AND code=? AND trade_date=? AND adjustment=?
                """,
                [
                    (
                        _record_hash(_record_from_storage_row(row)), row["market"],
                        row["instrument_type"], row["code"], row["trade_date"], row["adjustment"],
                    )
                    for row in rows
                ],
            )
        else:
            connection.executemany(
                """
                UPDATE market_daily_bar_observations SET data_hash=?
                WHERE refresh_id=? AND market=? AND instrument_type=? AND code=? AND trade_date=?
                """,
                [
                    (
                        _record_hash(_record_from_storage_row(row)), row["refresh_id"], row["market"],
                        row["instrument_type"], row["code"], row["trade_date"],
                    )
                    for row in rows
                ],
            )


def _backfill_split_hashes(connection: sqlite3.Connection) -> None:
    for table in ("market_daily_bars", "market_daily_bar_observations"):
        rows = connection.execute(f"SELECT rowid AS _rowid, * FROM {table}").fetchall()  # noqa: S608
        updates = [
            (
                _content_hash(record := _record_from_storage_row(row)),
                _provenance_hash(record),
                row["_rowid"],
            )
            for row in rows
        ]
        connection.executemany(
            f"UPDATE {table} SET content_hash=?, provenance_hash=? WHERE rowid=?",  # noqa: S608
            updates,
        )


def _drop_index(connection: sqlite3.Connection, name: str) -> None:
    connection.execute(f"DROP INDEX IF EXISTS {name}")


_LEGACY_MARKET_DAILY_TABLES = (
    "closing_prices",
    "closing_price_observations",
    "closing_price_capture_jobs",
)


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_schema WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _migrate_and_drop_legacy_closing_tables(connection: sqlite3.Connection) -> None:
    """合并旧 closing_* 表中的缺失记录，校验覆盖后删除重复表。"""
    existing = {table for table in _LEGACY_MARKET_DAILY_TABLES if _table_exists(connection, table)}
    if not existing:
        return

    connection.execute("BEGIN IMMEDIATE")
    try:
        if "closing_prices" in existing:
            connection.execute(
                """
                INSERT OR IGNORE INTO market_daily_bars (
                    market, instrument_type, code, name, trade_date, currency, open, high, low, close,
                    pre_close, change_amount, change_pct, volume, amount, adjustment, source,
                    source_quote_time, verification_status, first_refreshed_at, last_refreshed_at,
                    revision, data_hash
                )
                SELECT market, instrument_type, code, name, trade_date, currency, open, high, low, close,
                       pre_close, change_amount, change_pct, volume, amount, adjustment, source,
                       source_quote_time, verification_status, first_captured_at, last_captured_at,
                       revision, data_hash
                FROM closing_prices
                """
            )
            missing = connection.execute(
                """
                SELECT 1 FROM closing_prices AS legacy
                WHERE NOT EXISTS (
                    SELECT 1 FROM market_daily_bars AS current
                    WHERE current.market=legacy.market
                      AND current.instrument_type=legacy.instrument_type
                      AND current.code=legacy.code
                      AND current.trade_date=legacy.trade_date
                      AND current.adjustment=legacy.adjustment
                ) LIMIT 1
                """
            ).fetchone()
            if missing is not None:
                raise RuntimeError("旧版 closing_prices 未完整迁移，拒绝删除")

        if "closing_price_observations" in existing:
            connection.execute(
                """
                INSERT OR IGNORE INTO market_daily_bar_observations (
                    refresh_id, checkpoint, refreshed_at, market, instrument_type, code, name, trade_date,
                    currency, open, high, low, close, pre_close, change_amount, change_pct, volume, amount,
                    adjustment, source, source_quote_time, data_hash
                )
                SELECT legacy.capture_id, legacy.checkpoint, legacy.captured_at,
                       legacy.market, legacy.instrument_type, legacy.code, legacy.name,
                       legacy.trade_date, legacy.currency, legacy.open, legacy.high, legacy.low,
                       legacy.close, legacy.pre_close, legacy.change_amount, legacy.change_pct,
                       legacy.volume, legacy.amount, legacy.adjustment, legacy.source,
                       legacy.source_quote_time, legacy.data_hash
                FROM closing_price_observations AS legacy
                WHERE NOT EXISTS (
                    SELECT 1 FROM market_daily_bar_observations AS current
                    WHERE current.checkpoint=legacy.checkpoint
                      AND current.market=legacy.market
                      AND current.instrument_type=legacy.instrument_type
                      AND current.code=legacy.code
                      AND current.trade_date=legacy.trade_date
                      AND current.adjustment=legacy.adjustment
                      AND current.data_hash=legacy.data_hash
                )
                """
            )
            missing = connection.execute(
                """
                SELECT 1 FROM closing_price_observations AS legacy
                WHERE NOT EXISTS (
                    SELECT 1 FROM market_daily_bar_observations AS current
                    WHERE current.checkpoint=legacy.checkpoint
                      AND current.market=legacy.market
                      AND current.instrument_type=legacy.instrument_type
                      AND current.code=legacy.code
                      AND current.trade_date=legacy.trade_date
                      AND current.adjustment=legacy.adjustment
                      AND current.data_hash=legacy.data_hash
                ) LIMIT 1
                """
            ).fetchone()
            if missing is not None:
                raise RuntimeError("旧版 closing_price_observations 未完整迁移，拒绝删除")

        if "closing_price_capture_jobs" in existing:
            connection.execute(
                """
                INSERT OR IGNORE INTO market_daily_bar_refresh_jobs (
                    trade_date, checkpoint, segment, status, attempts, next_retry_at,
                    expected_count, stored_count, last_error, started_at, completed_at, updated_at
                )
                SELECT trade_date, checkpoint, segment, status, attempts, next_retry_at,
                       expected_count, stored_count, last_error, started_at, completed_at, updated_at
                FROM closing_price_capture_jobs
                """
            )
            missing = connection.execute(
                """
                SELECT 1 FROM closing_price_capture_jobs AS legacy
                WHERE NOT EXISTS (
                    SELECT 1 FROM market_daily_bar_refresh_jobs AS current
                    WHERE current.trade_date=legacy.trade_date
                      AND current.checkpoint=legacy.checkpoint
                      AND current.segment=legacy.segment
                ) LIMIT 1
                """
            ).fetchone()
            if missing is not None:
                raise RuntimeError("旧版 closing_price_capture_jobs 未完整迁移，拒绝删除")

        for table in _LEGACY_MARKET_DAILY_TABLES:
            if table in existing:
                connection.execute(f"DROP TABLE {table}")  # noqa: S608
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _migrate_legacy_bar_tables(connection: sqlite3.Connection) -> None:
    """将开发期旧列名/单值因子表在单事务内迁移为 v4。"""
    bar_columns = _table_columns(connection, "market_daily_bars")
    observation_columns = _table_columns(connection, "market_daily_bar_observations")
    migrate_bars = bool(bar_columns) and (
        "adjustment_factor" in bar_columns or "first_refreshed_at" not in bar_columns
    )
    migrate_observations = bool(observation_columns) and (
        "adjustment_factor" in observation_columns or "refresh_id" not in observation_columns
    )
    if not migrate_bars and not migrate_observations:
        return

    connection.execute("BEGIN IMMEDIATE")
    try:
        if migrate_bars:
            connection.execute("ALTER TABLE market_daily_bars RENAME TO market_daily_bars_v3_legacy")
            _drop_index(connection, "idx_market_daily_bars_date_market")
            _drop_index(connection, "idx_market_daily_bars_code_date")
        if migrate_observations:
            connection.execute(
                "ALTER TABLE market_daily_bar_observations RENAME TO market_daily_bar_observations_v3_legacy"
            )
            _drop_index(connection, "idx_market_daily_bar_observations_lookup")
        _execute_schema(connection)

        if migrate_bars:
            first_column = "first_refreshed_at" if "first_refreshed_at" in bar_columns else "first_captured_at"
            last_column = "last_refreshed_at" if "last_refreshed_at" in bar_columns else "last_captured_at"
            connection.execute(
                f"""
                INSERT INTO market_daily_bars (
                    market, instrument_type, code, name, trade_date, currency, open, high, low, close,
                    pre_close, change_amount, change_pct, volume, amount, adjustment, source,
                    source_quote_time, verification_status, first_refreshed_at, last_refreshed_at,
                    revision, data_hash
                )
                SELECT market, instrument_type, code, name, trade_date, currency, open, high, low, close,
                       pre_close, change_amount, change_pct, volume, amount, adjustment, source,
                       source_quote_time, verification_status, {first_column}, {last_column},
                       revision, data_hash
                FROM market_daily_bars_v3_legacy
                """
            )
            connection.execute("DROP TABLE market_daily_bars_v3_legacy")
        if migrate_observations:
            id_column = "refresh_id" if "refresh_id" in observation_columns else "capture_id"
            time_column = "refreshed_at" if "refreshed_at" in observation_columns else "captured_at"
            connection.execute(
                f"""
                INSERT INTO market_daily_bar_observations (
                    refresh_id, checkpoint, refreshed_at, market, instrument_type, code, name, trade_date,
                    currency, open, high, low, close, pre_close, change_amount, change_pct, volume, amount,
                    adjustment, source, source_quote_time, data_hash
                )
                SELECT {id_column}, checkpoint, {time_column}, market, instrument_type, code, name, trade_date,
                       currency, open, high, low, close, pre_close, change_amount, change_pct, volume, amount,
                       adjustment, source, source_quote_time, data_hash
                FROM market_daily_bar_observations_v3_legacy
                """
            )
            connection.execute("DROP TABLE market_daily_bar_observations_v3_legacy")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _deduplicate_equivalent_observations(connection: sqlite3.Connection) -> int:
    """移除同阶段、同标的、同内容的重复快照，保留最早一条审计记录。"""
    result = connection.execute(
        """
        DELETE FROM market_daily_bar_observations
        WHERE rowid IN (
            SELECT rowid FROM (
                SELECT rowid,
                       ROW_NUMBER() OVER (
                           PARTITION BY checkpoint, market, instrument_type, code,
                                        trade_date, adjustment, data_hash
                           ORDER BY refreshed_at, rowid
                       ) AS duplicate_rank
                FROM market_daily_bar_observations
            )
            WHERE duplicate_rank > 1
        )
        """
    )
    return max(0, result.rowcount)


def _deduplicate_business_observations(connection: sqlite3.Connection) -> int:
    """按行情内容去重，来源或发布时间变化不再复制整条快照。"""
    result = connection.execute(
        """
        DELETE FROM market_daily_bar_observations
        WHERE rowid IN (
            SELECT rowid FROM (
                SELECT rowid,
                       ROW_NUMBER() OVER (
                           PARTITION BY checkpoint, market, instrument_type, code,
                                        trade_date, adjustment,
                                        COALESCE(content_hash, data_hash)
                           ORDER BY refreshed_at, rowid
                       ) AS duplicate_rank
                FROM market_daily_bar_observations
            )
            WHERE duplicate_rank > 1
        )
        """
    )
    return max(0, result.rowcount)


def _migrate_allow_hk_corporate_actions_and_factors(connection: sqlite3.Connection) -> None:
    """把 market_corporate_actions / market_daily_adjustment_factors / market_adjustment_factor_state 的 CHECK 放开到 hk。"""
    action_sql_row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='market_corporate_actions'"
    ).fetchone()
    if action_sql_row and "market = 'cn'" in action_sql_row[0]:
        connection.execute(
            """
            CREATE TABLE market_corporate_actions_new (
                market          TEXT NOT NULL CHECK (market IN ('cn', 'hk')),
                code            TEXT NOT NULL,
                action_date     TEXT NOT NULL,
                sequence        INTEGER NOT NULL CHECK (sequence >= 0),
                category        INTEGER NOT NULL,
                category_name   TEXT NOT NULL DEFAULT '',
                cash_dividend   REAL NOT NULL DEFAULT 0,
                rights_shares   REAL NOT NULL DEFAULT 0,
                rights_price    REAL NOT NULL DEFAULT 0,
                bonus_shares    REAL NOT NULL DEFAULT 0,
                split_ratio     REAL NOT NULL DEFAULT 0,
                raw_json        TEXT NOT NULL,
                source          TEXT NOT NULL,
                action_hash     TEXT NOT NULL,
                refreshed_at    TEXT NOT NULL,
                PRIMARY KEY (market, code, action_date, sequence)
            )
            """
        )
        connection.execute(
            "INSERT INTO market_corporate_actions_new SELECT * FROM market_corporate_actions"
        )
        connection.execute("DROP TABLE market_corporate_actions")
        connection.execute(
            "ALTER TABLE market_corporate_actions_new RENAME TO market_corporate_actions"
        )
        connection.execute(
            "CREATE INDEX idx_market_corporate_actions_code_date "
            "ON market_corporate_actions(market, code, action_date DESC)"
        )

    factor_sql_row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='market_daily_adjustment_factors'"
    ).fetchone()
    if factor_sql_row and (
        "market = 'cn'" in factor_sql_row[0]
        or "hfq_multiplier  REAL NOT NULL" in factor_sql_row[0]
        or "hfq_multiplier REAL NOT NULL" in factor_sql_row[0]
    ):
        connection.execute(
            """
            CREATE TABLE market_daily_adjustment_factors_new (
                market          TEXT NOT NULL CHECK (market IN ('cn', 'hk')),
                code            TEXT NOT NULL,
                trade_date      TEXT NOT NULL,
                qfq_multiplier  REAL NOT NULL,
                qfq_offset      REAL NOT NULL,
                hfq_multiplier  REAL,
                hfq_offset      REAL,
                action_hash     TEXT NOT NULL,
                algorithm_version TEXT NOT NULL,
                source          TEXT NOT NULL,
                calculated_at   TEXT NOT NULL,
                PRIMARY KEY (market, code, trade_date)
            )
            """
        )
        connection.execute(
            "INSERT INTO market_daily_adjustment_factors_new SELECT * FROM market_daily_adjustment_factors"
        )
        connection.execute("DROP TABLE market_daily_adjustment_factors")
        connection.execute(
            "ALTER TABLE market_daily_adjustment_factors_new RENAME TO market_daily_adjustment_factors"
        )
        connection.execute(
            "CREATE INDEX idx_market_daily_adjustment_factors_code_date "
            "ON market_daily_adjustment_factors(market, code, trade_date DESC)"
        )

    state_sql_row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='market_adjustment_factor_state'"
    ).fetchone()
    if state_sql_row and "market = 'cn'" in state_sql_row[0]:
        connection.execute(
            """
            CREATE TABLE market_adjustment_factor_state_new (
                market          TEXT NOT NULL CHECK (market IN ('cn', 'hk')),
                code            TEXT NOT NULL,
                action_hash     TEXT NOT NULL,
                algorithm_version TEXT NOT NULL,
                source          TEXT NOT NULL,
                calculated_at   TEXT NOT NULL,
                last_checked_at TEXT NOT NULL,
                last_error      TEXT,
                using_last_good INTEGER NOT NULL DEFAULT 0 CHECK (using_last_good IN (0, 1)),
                factor_count    INTEGER NOT NULL CHECK (factor_count >= 0),
                PRIMARY KEY (market, code)
            )
            """
        )
        connection.execute(
            "INSERT INTO market_adjustment_factor_state_new SELECT * FROM market_adjustment_factor_state"
        )
        connection.execute("DROP TABLE market_adjustment_factor_state")
        connection.execute(
            "ALTER TABLE market_adjustment_factor_state_new RENAME TO market_adjustment_factor_state"
        )


@dataclass(frozen=True)
class MarketDailyAttemptLease:
    attempts: int
    attempt_id: str


class StaleMarketDailyAttemptError(RuntimeError):
    """任务租约已被更新的 worker 取代。"""


class _ConnectionScope:
    """复用连接的单次操作作用域，保持 ``with sqlite3.connect()`` 的提交/回滚语义。

    成功退出（无异常）提交；抛异常则回滚。方法内显式 ``BEGIN IMMEDIATE`` 的事务
    其结束时 ``in_transaction`` 为假，这里的 commit/rollback 都是无害的空操作。
    """

    __slots__ = ("_connection",)

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def __enter__(self) -> sqlite3.Connection:
        return self._connection

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if exc_type is not None:
            self._connection.rollback()
        elif self._connection.in_transaction:
            self._connection.commit()
        return False


# 线程本地连接：按 (线程, 库文件) 复用，避免每个方法都新建连接 + PRAGMA。
# 逐方法新建连接 = 一次盘中 K 线读取开约 7 个连接。
_local = threading.local()
_close_lock = threading.Lock()
_open_connections: list[sqlite3.Connection] = []
_initialized_paths: set[str] = set()


def close_all_connections() -> None:
    """关闭所有复用的连接并清空初始化标记（进程退出或文件被替换后调用）。"""
    with _close_lock:
        connections = list(_open_connections)
        _open_connections.clear()
        _initialized_paths.clear()
    for connection in connections:
        try:
            if connection.in_transaction:
                connection.rollback()
            connection.close()
        except Exception:  # noqa: BLE001 - 关闭清理不应抛出
            pass
    _local.connections = {}


class MarketDailyBarRepository:
    """复用线程本地连接；每次操作在连接上开一个作用域事务。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _connection(self) -> sqlite3.Connection:
        key = str(self.path)
        connections = getattr(_local, "connections", None)
        if connections is None:
            connections = {}
            _local.connections = connections
        connection = connections.get(key)
        if connection is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.path.parent.chmod(0o700)
            except OSError:
                pass
            connection = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            try:
                self.path.chmod(0o600)
            except OSError:
                pass
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")
            connections[key] = connection
            with _close_lock:
                _open_connections.append(connection)
        return connection

    def _connect(self) -> _ConnectionScope:
        return _ConnectionScope(self._connection())

    def initialize(self) -> None:
        key = str(self.path)
        with _close_lock:
            if key in _initialized_paths:
                return
        with self._connect() as connection:
            _execute_schema(connection)
            state_columns = _table_columns(connection, "market_adjustment_factor_state")
            if "last_checked_at" not in state_columns:
                connection.execute(
                    "ALTER TABLE market_adjustment_factor_state ADD COLUMN last_checked_at TEXT"
                )
                connection.execute(
                    "UPDATE market_adjustment_factor_state SET last_checked_at=calculated_at "
                    "WHERE last_checked_at IS NULL"
                )
            if "last_error" not in state_columns:
                connection.execute(
                    "ALTER TABLE market_adjustment_factor_state ADD COLUMN last_error TEXT"
                )
            if "using_last_good" not in state_columns:
                connection.execute(
                    "ALTER TABLE market_adjustment_factor_state ADD COLUMN using_last_good INTEGER NOT NULL DEFAULT 0"
                )
            job_columns = _table_columns(connection, "market_daily_bar_refresh_jobs")
            for column in ("attempt_id", "lease_expires_at", "worker_id"):
                if column not in job_columns:
                    connection.execute(
                        f"ALTER TABLE market_daily_bar_refresh_jobs ADD COLUMN {column} TEXT"
                    )
            for table in ("market_daily_bars", "market_daily_bar_observations"):
                columns = _table_columns(connection, table)
                for column in ("content_hash", "provenance_hash"):
                    if column not in columns:
                        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
                if "turnover_pct" not in columns:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN turnover_pct REAL")
            _migrate_allow_hk_corporate_actions_and_factors(connection)
            _record_migration_ledger(connection, 1)
            connection.execute("PRAGMA user_version=1")
        with _close_lock:
            _initialized_paths.add(key)

    def claim_attempt(
        self,
        trade_date: date,
        checkpoint: RefreshCheckpoint,
        segment: str,
        *,
        started_at: datetime | None = None,
        worker_id: str | None = None,
        force: bool = False,
        lease_seconds: int = 30 * 60,
    ) -> MarketDailyAttemptLease | None:
        """在单个写事务中判断到期状态并领取任务租约。"""
        now_value = started_at or _utc_now()
        now = _iso(now_value)
        lease_expires = _iso(now_value + timedelta(seconds=lease_seconds))
        attempt_id = uuid4().hex
        key = (trade_date.isoformat(), checkpoint, segment)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT status, attempts, next_retry_at, started_at, lease_expires_at, attempt_id
                FROM market_daily_bar_refresh_jobs
                WHERE trade_date=? AND checkpoint=? AND segment=?
                """,
                key,
            ).fetchone()
            if row is not None and not force:
                status = str(row["status"])
                if status in {"success", "skipped"}:
                    return None
                if status == "failed" and row["next_retry_at"]:
                    retry_at = datetime.fromisoformat(row["next_retry_at"])
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=UTC)
                    if now_value.astimezone(UTC) < retry_at.astimezone(UTC):
                        return None
                if status == "running":
                    expiry_text = row["lease_expires_at"]
                    if expiry_text:
                        expiry = datetime.fromisoformat(expiry_text)
                    elif row["started_at"]:
                        expiry = datetime.fromisoformat(row["started_at"]) + timedelta(minutes=30)
                    else:
                        expiry = None
                    if expiry is not None:
                        if expiry.tzinfo is None:
                            expiry = expiry.replace(tzinfo=UTC)
                        if now_value.astimezone(UTC) < expiry.astimezone(UTC):
                            return None
            previous_attempt_id = str(row["attempt_id"]) if row is not None and row["attempt_id"] else None
            if row is not None and row["status"] == "running" and previous_attempt_id:
                connection.execute(
                    """
                    UPDATE market_daily_refresh_attempts
                    SET status='superseded', completed_at=?,
                        error_message='lease expired or force-refreshed'
                    WHERE attempt_id=? AND status='running'
                    """,
                    (now, previous_attempt_id),
                )
            if row is None:
                attempts = 1
                connection.execute(
                    """
                    INSERT INTO market_daily_bar_refresh_jobs (
                        trade_date, checkpoint, segment, status, attempts, started_at,
                        attempt_id, lease_expires_at, worker_id, updated_at
                    ) VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?, ?)
                    """,
                    (*key, attempts, now, attempt_id, lease_expires, worker_id, now),
                )
            else:
                attempts = int(row["attempts"]) + 1
                connection.execute(
                    """
                    UPDATE market_daily_bar_refresh_jobs
                    SET status='running', attempts=?, started_at=?, completed_at=NULL,
                        next_retry_at=NULL, last_error=NULL, attempt_id=?,
                        lease_expires_at=?, worker_id=?, updated_at=?
                    WHERE trade_date=? AND checkpoint=? AND segment=?
                    """,
                    (attempts, now, attempt_id, lease_expires, worker_id, now, *key),
                )
            connection.execute(
                """
                INSERT INTO market_daily_refresh_attempts (
                    attempt_id, trade_date, checkpoint, segment, attempt_no,
                    worker_id, status, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'running', ?)
                """,
                (attempt_id, *key, attempts, worker_id, now),
            )
        return MarketDailyAttemptLease(attempts=attempts, attempt_id=attempt_id)

    def start_attempt(
        self,
        trade_date: date,
        checkpoint: RefreshCheckpoint,
        segment: str,
        *,
        started_at: datetime | None = None,
    ) -> int:
        """兼容管理和测试调用；强制开启一个新的任务租约。"""
        lease = self.claim_attempt(
            trade_date, checkpoint, segment, started_at=started_at, force=True
        )
        if lease is None:  # pragma: no cover - force 领取必定成功
            raise RuntimeError(f"无法领取市场日行情任务: {trade_date}/{checkpoint}/{segment}")
        return lease.attempts

    def record_failure(
        self,
        trade_date: date,
        checkpoint: RefreshCheckpoint,
        segment: str,
        error: Exception,
        next_retry_at: datetime,
        *,
        attempt_id: str | None = None,
    ) -> bool:
        now = _iso(_utc_now())
        message = f"{type(error).__name__}: {error}"[:1000]
        with self._connect() as connection:
            effective_attempt_id = attempt_id
            if effective_attempt_id is None:
                row = connection.execute(
                    """
                    SELECT attempt_id FROM market_daily_bar_refresh_jobs
                    WHERE trade_date=? AND checkpoint=? AND segment=?
                    """,
                    (trade_date.isoformat(), checkpoint, segment),
                ).fetchone()
                effective_attempt_id = row["attempt_id"] if row else None
            result = connection.execute(
                """
                UPDATE market_daily_bar_refresh_jobs
                SET status='failed', next_retry_at=?, last_error=?, completed_at=?,
                    lease_expires_at=NULL, updated_at=?
                WHERE trade_date=? AND checkpoint=? AND segment=?
                  AND (? IS NULL OR attempt_id=?)
                """,
                (
                    _iso(next_retry_at), message, now, now, trade_date.isoformat(),
                    checkpoint, segment, attempt_id, attempt_id,
                ),
            )
            if result.rowcount == 1 and effective_attempt_id is not None:
                connection.execute(
                    """
                    UPDATE market_daily_refresh_attempts
                    SET status='failed', completed_at=?, next_retry_at=?, error_message=?
                    WHERE attempt_id=?
                    """,
                    (now, _iso(next_retry_at), message, effective_attempt_id),
                )
        return result.rowcount == 1

    def record_skipped(
        self,
        trade_date: date,
        checkpoint: RefreshCheckpoint,
        segment: str,
        note: str,
        *,
        attempt_id: str | None = None,
    ) -> bool:
        now = _iso(_utc_now())
        with self._connect() as connection:
            effective_attempt_id = attempt_id
            if effective_attempt_id is None:
                row = connection.execute(
                    """
                    SELECT attempt_id FROM market_daily_bar_refresh_jobs
                    WHERE trade_date=? AND checkpoint=? AND segment=?
                    """,
                    (trade_date.isoformat(), checkpoint, segment),
                ).fetchone()
                effective_attempt_id = row["attempt_id"] if row else None
            result = connection.execute(
                """
                UPDATE market_daily_bar_refresh_jobs
                SET status='skipped', stored_count=0, expected_count=0, last_error=?,
                    next_retry_at=NULL, completed_at=?, lease_expires_at=NULL, updated_at=?
                WHERE trade_date=? AND checkpoint=? AND segment=?
                  AND (? IS NULL OR attempt_id=?)
                """,
                (
                    note[:1000], now, now, trade_date.isoformat(), checkpoint, segment,
                    attempt_id, attempt_id,
                ),
            )
            if result.rowcount == 1 and attempt_id is not None:
                connection.execute(
                    """
                    UPDATE market_daily_refresh_attempts
                    SET status='skipped', completed_at=?, error_message=?
                    WHERE attempt_id=?
                    """,
                    (now, note[:1000], effective_attempt_id),
                )
        return result.rowcount == 1

    def persist_refresh(
        self,
        trade_date: date,
        checkpoint: RefreshCheckpoint,
        segment: str,
        records: Iterable[MarketDailyBarRecord],
        *,
        refreshed_at: datetime | None = None,
        attempt_id: str | None = None,
        source: str = "unknown",
    ) -> int:
        rows = [
            MarketDailyBarRecord.model_validate(record.model_dump())
            for record in records
        ]
        if not rows:
            raise ValueError(f"{segment} 市场日行情为空")
        if any(record.trade_date != trade_date for record in rows):
            raise ValueError(f"{segment} 存在非目标交易日数据")
        segment_pairs = {
            "cn_stock": ("cn", "stock"),
            "cn_index": ("cn", "index"),
            "hk_stock": ("hk", "stock"),
            "hk_index": ("hk", "index"),
        }
        expected_pair = segment_pairs.get(segment)
        if expected_pair is None:
            raise ValueError(f"未知市场日行情分区: {segment}")
        if any((record.market, record.instrument_type) != expected_pair for record in rows):
            raise ValueError(f"{segment} 包含其他市场或品种数据")
        keys = [
            (record.market, record.instrument_type, record.code, record.trade_date, record.adjustment)
            for record in rows
        ]
        if len(keys) != len(set(keys)):
            raise ValueError(f"{segment} 包含重复证券记录")

        refresh_id = uuid4().hex
        captured = _iso(refreshed_at or _utc_now())
        verification = "confirmed" if checkpoint == "recheck" else "provisional"
        prepared: list[tuple[tuple[object, ...], str, str, str]] = []
        for record in rows:
            values: tuple[object, ...] = (
                record.market, record.instrument_type, record.code, record.name,
                record.trade_date.isoformat(), record.currency, record.open, record.high,
                record.low, record.close, record.pre_close, record.change_amount,
                record.change_pct, record.volume, record.amount, record.turnover_pct,
                record.adjustment, record.source, _iso(record.source_quote_time),
            )
            prepared.append((
                values, _record_hash(record), _content_hash(record), _provenance_hash(record)
            ))
        batch_hash = hashlib.sha256(
            "".join(sorted(content_hash for _, _, content_hash, _ in prepared)).encode()
        ).hexdigest()

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if attempt_id is not None:
                active = connection.execute(
                    """
                    SELECT 1 FROM market_daily_bar_refresh_jobs
                    WHERE trade_date=? AND checkpoint=? AND segment=?
                      AND status='running' AND attempt_id=?
                    """,
                    (trade_date.isoformat(), checkpoint, segment, attempt_id),
                ).fetchone()
                if active is None:
                    raise StaleMarketDailyAttemptError(
                        f"市场日行情任务租约已失效: {trade_date}/{checkpoint}/{segment}"
                    )
            effective_attempt_id = attempt_id
            if effective_attempt_id is None:
                current_job = connection.execute(
                    """
                    SELECT attempt_id FROM market_daily_bar_refresh_jobs
                    WHERE trade_date=? AND checkpoint=? AND segment=?
                    """,
                    (trade_date.isoformat(), checkpoint, segment),
                ).fetchone()
                effective_attempt_id = current_job["attempt_id"] if current_job else None

            existing_rows = connection.execute(
                """
                SELECT market, instrument_type, code, trade_date, adjustment,
                       content_hash, provenance_hash, verification_status
                FROM market_daily_bars
                WHERE trade_date=?
                """,
                (trade_date.isoformat(),),
            ).fetchall()
            existing = {
                (row["market"], row["instrument_type"], row["code"],
                 row["trade_date"], row["adjustment"]):
                (row["content_hash"], row["provenance_hash"], row["verification_status"])
                for row in existing_rows
            }
            initial_baseline_exists = connection.execute(
                """
                SELECT 1 FROM market_daily_refresh_runs
                WHERE trade_date=? AND checkpoint='initial' AND segment=?
                UNION ALL
                SELECT 1 FROM market_daily_bar_observations
                WHERE trade_date=? AND checkpoint='initial'
                  AND market=? AND instrument_type=?
                LIMIT 1
                """,
                (
                    trade_date.isoformat(), segment, trade_date.isoformat(),
                    expected_pair[0], expected_pair[1],
                ),
            ).fetchone() is not None
            store_full_baseline = checkpoint == "initial" and not initial_baseline_exists
            inserted = updated = unchanged = ignored = 0
            observation_values: list[tuple[object, ...]] = []
            upsert_values: list[tuple[object, ...]] = []
            for values, data_hash, content_hash, provenance_hash in prepared:
                key = (values[0], values[1], values[2], values[4], values[16])
                previous = existing.get(key)
                is_ignored = bool(
                    previous and previous[2] == "confirmed" and verification == "provisional"
                )
                is_changed = previous is None or previous[0] != content_hash
                if previous is None:
                    inserted += 1
                elif is_ignored:
                    ignored += 1
                elif is_changed:
                    updated += 1
                else:
                    unchanged += 1
                # 首次 initial 保存完整基线；后续 initial/recheck/重试只保存变化。
                if store_full_baseline or is_changed:
                    observation_values.append(
                        (refresh_id, checkpoint, captured, *values, data_hash, content_hash, provenance_hash)
                    )
                upsert_values.append(
                    (*values, verification, captured, captured, data_hash, content_hash, provenance_hash)
                )

            connection.executemany(
                """
                INSERT INTO market_daily_bar_observations (
                    refresh_id, checkpoint, refreshed_at, market, instrument_type, code, name,
                    trade_date, currency, open, high, low, close, pre_close, change_amount,
                    change_pct, volume, amount, turnover_pct, adjustment, source, source_quote_time, data_hash,
                    content_hash, provenance_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                observation_values,
            )
            connection.executemany(
                """
                INSERT INTO market_daily_bars (
                    market, instrument_type, code, name, trade_date, currency, open, high, low,
                    close, pre_close, change_amount, change_pct, volume, amount, turnover_pct, adjustment,
                    source, source_quote_time, verification_status, first_refreshed_at,
                    last_refreshed_at, revision, data_hash, content_hash, provenance_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(market, instrument_type, code, trade_date, adjustment) DO UPDATE SET
                    name=excluded.name, currency=excluded.currency, open=excluded.open,
                    high=excluded.high, low=excluded.low, close=excluded.close,
                    pre_close=excluded.pre_close, change_amount=excluded.change_amount,
                    change_pct=excluded.change_pct, volume=excluded.volume, amount=excluded.amount,
                    turnover_pct=excluded.turnover_pct,
                    source=excluded.source, source_quote_time=excluded.source_quote_time,
                    verification_status=CASE
                        WHEN excluded.verification_status='confirmed' THEN 'confirmed'
                        ELSE market_daily_bars.verification_status
                    END,
                    last_refreshed_at=excluded.last_refreshed_at,
                    revision=market_daily_bars.revision + CASE
                        WHEN market_daily_bars.content_hash <> excluded.content_hash THEN 1 ELSE 0 END,
                    data_hash=excluded.data_hash, content_hash=excluded.content_hash,
                    provenance_hash=excluded.provenance_hash
                WHERE NOT (
                    market_daily_bars.verification_status='confirmed'
                    AND excluded.verification_status='provisional'
                )
                """,
                upsert_values,
            )
            stored = inserted + updated
            result = connection.execute(
                """
                UPDATE market_daily_bar_refresh_jobs
                SET status='success', expected_count=?, stored_count=?, next_retry_at=NULL,
                    last_error=NULL, completed_at=?, lease_expires_at=NULL, updated_at=?
                WHERE trade_date=? AND checkpoint=? AND segment=?
                  AND (? IS NULL OR attempt_id=?)
                """,
                (
                    len(rows), stored, captured, captured, trade_date.isoformat(),
                    checkpoint, segment, attempt_id, attempt_id,
                ),
            )
            if result.rowcount != 1:
                raise StaleMarketDailyAttemptError(
                    f"市场日行情刷新任务不存在或租约失效: "
                    f"{trade_date}/{checkpoint}/{segment}"
                )
            connection.execute(
                """
                INSERT INTO market_daily_refresh_runs (
                    refresh_id, attempt_id, trade_date, checkpoint, segment, source,
                    received_count, inserted_count, updated_count, unchanged_count,
                    ignored_count, observation_count, batch_hash, refreshed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    refresh_id, effective_attempt_id, trade_date.isoformat(), checkpoint, segment, source,
                    len(rows), inserted, updated, unchanged, ignored,
                    len(observation_values), batch_hash, captured,
                ),
            )
            if attempt_id is not None:
                connection.execute(
                    """
                    UPDATE market_daily_refresh_attempts
                    SET status='success', completed_at=? WHERE attempt_id=?
                    """,
                    (captured, effective_attempt_id),
                )
        return stored

    def should_attempt(
        self,
        trade_date: date,
        checkpoint: RefreshCheckpoint,
        segment: str,
        now: datetime,
    ) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status, next_retry_at, started_at FROM market_daily_bar_refresh_jobs WHERE trade_date=? AND checkpoint=? AND segment=?",
                (trade_date.isoformat(), checkpoint, segment),
            ).fetchone()
        if row is None:
            return True
        if row["status"] in {"success", "skipped"}:
            return False
        if row["status"] == "running":
            started_at = datetime.fromisoformat(row["started_at"]) if row["started_at"] else None
            # 进程若在写入中途退出，running 不应永久阻止补采。30 分钟内仍视为
            # 正常在途，超过后由下一轮安全重试（最终写入按唯一键幂等 upsert）。
            return started_at is None or now >= started_at + timedelta(minutes=30)
        retry_at = datetime.fromisoformat(row["next_retry_at"]) if row["next_retry_at"] else None
        return retry_at is None or now >= retry_at

    def list_bars(
        self,
        *,
        market: str,
        instrument_type: str,
        code: str,
        start_date: date,
        end_date: date,
    ) -> list[MarketDailyBar]:
        """按标的和日期范围读取本地日行情，不附加确认时间判断。"""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM market_daily_bars
                WHERE market=? AND instrument_type=? AND code=?
                  AND trade_date>=? AND trade_date<=?
                ORDER BY trade_date
                """,
                (market, instrument_type, code, start_date.isoformat(), end_date.isoformat()),
            ).fetchall()
        return [_row_to_price(row) for row in rows]

    def reset_job(
        self,
        trade_date: date,
        checkpoint: RefreshCheckpoint,
        segment: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM market_daily_bar_refresh_jobs WHERE trade_date=? AND checkpoint=? AND segment=?",
                (trade_date.isoformat(), checkpoint, segment),
            )

    def prune_audit_history(
        self,
        *,
        observations_before: date,
        attempts_before: date,
    ) -> tuple[int, int, int]:
        """清理过期审计明细；主行情、刷新任务当前状态和公司行为不受影响。"""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            observations = connection.execute(
                "DELETE FROM market_daily_bar_observations WHERE trade_date<?",
                (observations_before.isoformat(),),
            ).rowcount
            runs = connection.execute(
                "DELETE FROM market_daily_refresh_runs WHERE trade_date<?",
                (attempts_before.isoformat(),),
            ).rowcount
            attempts = connection.execute(
                "DELETE FROM market_daily_refresh_attempts WHERE trade_date<?",
                (attempts_before.isoformat(),),
            ).rowcount
        return max(0, observations), max(0, runs), max(0, attempts)

    def optimize_storage(self) -> dict[str, int]:
        """执行轻量统计与 WAL checkpoint；不在在线流程执行阻塞式 VACUUM。"""
        with self._connect() as connection:
            connection.execute("PRAGMA optimize")
            checkpoint = connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
            freelist_count = int(connection.execute("PRAGMA freelist_count").fetchone()[0])
        return {
            "wal_busy": int(checkpoint[0]),
            "wal_pages": int(checkpoint[1]),
            "checkpointed_pages": int(checkpoint[2]),
            "page_count": page_count,
            "freelist_count": freelist_count,
        }

    def list_refresh_history(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[MarketDailyBarRefreshStatus], int]:
        clauses: list[str] = []
        parameters: list[object] = []
        if start_date is not None:
            clauses.append("trade_date>=?")
            parameters.append(start_date.isoformat())
        if end_date is not None:
            clauses.append("trade_date<=?")
            parameters.append(end_date.isoformat())
        if status is not None:
            clauses.append("status=?")
            parameters.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            total = int(connection.execute(
                f"SELECT COUNT(*) FROM market_daily_bar_refresh_jobs {where}",  # noqa: S608
                parameters,
            ).fetchone()[0])
            rows = connection.execute(
                f"""
                SELECT * FROM market_daily_bar_refresh_jobs {where}
                ORDER BY trade_date DESC, checkpoint DESC, segment
                LIMIT ? OFFSET ?
                """,  # noqa: S608
                [*parameters, limit, offset],
            ).fetchall()
        return [MarketDailyBarRefreshStatus.model_validate(dict(row)) for row in rows], total

    def delete_day(
        self,
        trade_date: date,
        *,
        segments: Sequence[str] | None = None,
    ) -> tuple[int, int, int]:
        segment_pairs = {
            "cn_stock": ("cn", "stock"),
            "cn_index": ("cn", "index"),
            "hk_stock": ("hk", "stock"),
            "hk_index": ("hk", "index"),
        }
        selected = list(segments or segment_pairs)
        pairs = [segment_pairs[segment] for segment in selected]
        bar_filter = " OR ".join("(market=? AND instrument_type=?)" for _ in pairs)
        bar_parameters: list[object] = [trade_date.isoformat()]
        for market, instrument_type in pairs:
            bar_parameters.extend((market, instrument_type))
        segment_placeholders = ",".join("?" for _ in selected)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            affected_cn_codes: list[str] = []
            if "cn_stock" in selected:
                affected_cn_codes = [
                    str(row["code"])
                    for row in connection.execute(
                        """
                        SELECT DISTINCT code FROM market_daily_bars
                        WHERE market='cn' AND instrument_type='stock' AND trade_date=?
                        """,
                        (trade_date.isoformat(),),
                    ).fetchall()
                ]
                connection.execute(
                    "DELETE FROM market_daily_adjustment_factors WHERE market='cn' AND trade_date=?",
                    (trade_date.isoformat(),),
                )
                if affected_cn_codes:
                    placeholders = ",".join("?" for _ in affected_cn_codes)
                    connection.execute(
                        f"DELETE FROM market_adjustment_factor_state WHERE market='cn' AND code IN ({placeholders})",  # noqa: S608
                        affected_cn_codes,
                    )
            observations = connection.execute(
                f"DELETE FROM market_daily_bar_observations WHERE trade_date=? AND ({bar_filter})",  # noqa: S608
                bar_parameters,
            ).rowcount
            bars = connection.execute(
                f"DELETE FROM market_daily_bars WHERE trade_date=? AND ({bar_filter})",  # noqa: S608
                bar_parameters,
            ).rowcount
            connection.execute(
                f"DELETE FROM market_daily_refresh_runs WHERE trade_date=? AND segment IN ({segment_placeholders})",  # noqa: S608
                [trade_date.isoformat(), *selected],
            )
            connection.execute(
                f"DELETE FROM market_daily_refresh_attempts WHERE trade_date=? AND segment IN ({segment_placeholders})",  # noqa: S608
                [trade_date.isoformat(), *selected],
            )
            jobs = connection.execute(
                f"DELETE FROM market_daily_bar_refresh_jobs WHERE trade_date=? AND segment IN ({segment_placeholders})",  # noqa: S608
                [trade_date.isoformat(), *selected],
            ).rowcount
        return max(0, bars), max(0, observations), max(0, jobs)

    def list_status(self, trade_date: date) -> list[MarketDailyBarRefreshStatus]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM market_daily_bar_refresh_jobs
                WHERE trade_date=? ORDER BY checkpoint, segment
                """,
                (trade_date.isoformat(),),
            ).fetchall()
        return [MarketDailyBarRefreshStatus.model_validate(dict(row)) for row in rows]

    def list_stock_dates(self, code: str) -> list[date]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT trade_date FROM market_daily_bars
                WHERE market='cn' AND instrument_type='stock' AND code=?
                ORDER BY trade_date
                """,
                (code,),
            ).fetchall()
        return [date.fromisoformat(row["trade_date"]) for row in rows]

    def get_factor_state(self, code: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM market_adjustment_factor_state WHERE market='cn' AND code=?",
                (code,),
            ).fetchone()
        return dict(row) if row else None

    def list_confirmed_closes(
        self,
        codes: list[str],
        trade_date: str,
    ) -> dict[str, dict[str, object]]:
        """批量读取指定交易日**已确认**的收盘数据。

        ``verification_status='confirmed'`` 由 recheck 检查点写入，而 recheck 只在
        17:00 之后触发——因此这个条件本身就等价于"当日已定稿"，无需再判断时间。
        16:20~17:00 之间只有 provisional，这里查不到任何行，兜底自然不生效。

        同时返回前一个交易日收盘，用于补 ``change_pct``（库里该列常为 NULL）。
        """
        if not codes:
            return {}
        result: dict[str, dict[str, object]] = {}
        with self._connect() as connection:
            placeholders = ",".join("?" * len(codes))
            rows = connection.execute(
                f"""
                SELECT code, close, amount, turnover_pct
                FROM market_daily_bars
                WHERE market='cn' AND instrument_type='stock'
                  AND verification_status='confirmed'
                  AND trade_date=?
                  AND code IN ({placeholders})
                """,
                (trade_date, *codes),
            ).fetchall()
            for row in rows:
                result[str(row["code"])] = {
                    "close": row["close"],
                    "amount": row["amount"],
                    "turnover_pct": row["turnover_pct"],
                }
            if not result:
                return {}
            # 前一交易日收盘：用于计算涨跌幅（库里 change_pct 多为 NULL）
            previous_rows = connection.execute(
                f"""
                SELECT code, close FROM (
                    SELECT code, close, MAX(trade_date) AS trade_date
                    FROM market_daily_bars
                    WHERE market='cn' AND instrument_type='stock'
                      AND verification_status='confirmed'
                      AND trade_date < ?
                      AND code IN ({placeholders})
                    GROUP BY code
                )
                """,
                (trade_date, *codes),
            ).fetchall()
            previous = {str(row["code"]): row["close"] for row in previous_rows}
        for code, payload in result.items():
            payload["pre_close"] = previous.get(code)
        return result

    def get_adjustment_summary(self, code: str, market: str = "cn") -> dict[str, object]:
        with self._connect() as connection:
            bars = connection.execute(
                """
                SELECT COUNT(*) AS count, MIN(trade_date) AS first_date, MAX(trade_date) AS last_date
                FROM market_daily_bars
                WHERE market=? AND instrument_type='stock' AND code=?
                """,
                (market, code),
            ).fetchone()
            factors = connection.execute(
                """
                SELECT COUNT(*) AS count, MIN(trade_date) AS first_date, MAX(trade_date) AS last_date
                FROM market_daily_adjustment_factors
                WHERE market=? AND code=?
                """,
                (market, code),
            ).fetchone()
            actions = connection.execute(
                "SELECT COUNT(*) AS count FROM market_corporate_actions WHERE market=? AND code=?",
                (market, code),
            ).fetchone()
            state = connection.execute(
                "SELECT * FROM market_adjustment_factor_state WHERE market=? AND code=?",
                (market, code),
            ).fetchone()
        return {
            "bar_count": int(bars["count"]),
            "first_bar_date": bars["first_date"],
            "last_bar_date": bars["last_date"],
            "factor_count": int(factors["count"]),
            "first_factor_date": factors["first_date"],
            "last_factor_date": factors["last_date"],
            "action_count": int(actions["count"]),
            "state": dict(state) if state else None,
        }

    def invalidate_adjustment_factors(self, code: str, market: str = "cn") -> tuple[int, int]:
        """删除衍生因子及状态；保留公司行为审计记录，下一次请求重新核验 XDXR。"""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            factors = connection.execute(
                "DELETE FROM market_daily_adjustment_factors WHERE market=? AND code=?",
                (market, code),
            ).rowcount
            state = connection.execute(
                "DELETE FROM market_adjustment_factor_state WHERE market=? AND code=?",
                (market, code),
            ).rowcount
        return max(0, factors), max(0, state)

    def count_corporate_actions(self, code: str, market: str = "cn") -> int:
        with self._connect() as connection:
            return int(connection.execute(
                "SELECT COUNT(*) FROM market_corporate_actions WHERE market=? AND code=?",
                (market, code),
            ).fetchone()[0])

    def mark_factor_check(
        self,
        code: str,
        checked_at: datetime,
        *,
        error: str | None = None,
        using_last_good: bool = False,
        market: str = "cn",
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE market_adjustment_factor_state
                SET last_checked_at=?, last_error=?, using_last_good=?
                WHERE market=? AND code=?
                """,
                (_iso(checked_at), error[:1000] if error else None, int(using_last_good), market, code),
            )

    def replace_adjustment_data(
        self,
        code: str,
        *,
        actions: list[MarketCorporateAction],
        factors: list[MarketDailyAdjustmentFactor],
        action_hash: str,
        algorithm_version: str,
        source: str,
        calculated_at: datetime,
        market: str = "cn",
    ) -> None:
        calculated = _iso(calculated_at)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM market_corporate_actions WHERE market=? AND code=?",
                (market, code),
            )
            connection.execute(
                "DELETE FROM market_daily_adjustment_factors WHERE market=? AND code=?",
                (market, code),
            )
            connection.executemany(
                """
                INSERT INTO market_corporate_actions (
                    market, code, action_date, sequence, category, category_name,
                    cash_dividend, rights_shares, rights_price, bonus_shares, split_ratio,
                    raw_json, source, action_hash, refreshed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        action.market, action.code, action.action_date.isoformat(), action.sequence,
                        action.category, action.category_name, action.cash_dividend,
                        action.rights_shares, action.rights_price, action.bonus_shares,
                        action.split_ratio, action.raw_json, action.source, action_hash, calculated,
                    )
                    for action in actions
                ],
            )
            connection.executemany(
                """
                INSERT INTO market_daily_adjustment_factors (
                    market, code, trade_date, qfq_multiplier, qfq_offset,
                    hfq_multiplier, hfq_offset, action_hash, algorithm_version, source, calculated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        factor.market, factor.code, factor.trade_date.isoformat(),
                        factor.qfq_multiplier, factor.qfq_offset, factor.hfq_multiplier,
                        factor.hfq_offset, factor.action_hash, factor.algorithm_version,
                        factor.source, _iso(factor.calculated_at),
                    )
                    for factor in factors
                ],
            )
            connection.execute(
                """
                INSERT INTO market_adjustment_factor_state (
                    market, code, action_hash, algorithm_version, source, calculated_at,
                    last_checked_at, last_error, using_last_good, factor_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0, ?)
                ON CONFLICT(market, code) DO UPDATE SET
                    action_hash=excluded.action_hash, algorithm_version=excluded.algorithm_version,
                    source=excluded.source, calculated_at=excluded.calculated_at,
                    last_checked_at=excluded.last_checked_at, last_error=NULL, using_last_good=0,
                    factor_count=excluded.factor_count
                """,
                (market, code, action_hash, algorithm_version, source, calculated, calculated, len(factors)),
            )

    def replace_adjustment_factors(
        self,
        code: str,
        *,
        factors: list[MarketDailyAdjustmentFactor],
        factor_hash: str,
        algorithm_version: str,
        source: str,
        calculated_at: datetime,
        market: str = "cn",
    ) -> None:
        """替换衍生因子和状态，但保留既有公司行为审计记录。"""
        calculated = _iso(calculated_at)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM market_daily_adjustment_factors WHERE market=? AND code=?",
                (market, code),
            )
            connection.executemany(
                """
                INSERT INTO market_daily_adjustment_factors (
                    market, code, trade_date, qfq_multiplier, qfq_offset,
                    hfq_multiplier, hfq_offset, action_hash, algorithm_version, source, calculated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        factor.market, factor.code, factor.trade_date.isoformat(),
                        factor.qfq_multiplier, factor.qfq_offset, factor.hfq_multiplier,
                        factor.hfq_offset, factor.action_hash, factor.algorithm_version,
                        factor.source, _iso(factor.calculated_at),
                    )
                    for factor in factors
                ],
            )
            connection.execute(
                """
                INSERT INTO market_adjustment_factor_state (
                    market, code, action_hash, algorithm_version, source, calculated_at,
                    last_checked_at, last_error, using_last_good, factor_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0, ?)
                ON CONFLICT(market, code) DO UPDATE SET
                    action_hash=excluded.action_hash, algorithm_version=excluded.algorithm_version,
                    source=excluded.source, calculated_at=excluded.calculated_at,
                    last_checked_at=excluded.last_checked_at, last_error=NULL, using_last_good=0,
                    factor_count=excluded.factor_count
                """,
                (market, code, factor_hash, algorithm_version, source, calculated, calculated, len(factors)),
            )

    def list_adjustment_factor_dates(self, code: str, market: str = "cn") -> list[date]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT trade_date FROM market_daily_adjustment_factors
                WHERE market=? AND code=? ORDER BY trade_date
                """,
                (market, code),
            ).fetchall()
        return [date.fromisoformat(row["trade_date"]) for row in rows]

    def list_adjustment_factors(
        self,
        code: str,
        start_date: date,
        end_date: date,
        market: str = "cn",
    ) -> list[MarketDailyAdjustmentFactor]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM market_daily_adjustment_factors
                WHERE market=? AND code=? AND trade_date>=? AND trade_date<=?
                ORDER BY trade_date
                """,
                (market, code, start_date.isoformat(), end_date.isoformat()),
            ).fetchall()
        return [
            MarketDailyAdjustmentFactor(
                market=row["market"], code=row["code"], trade_date=date.fromisoformat(row["trade_date"]),
                qfq_multiplier=row["qfq_multiplier"], qfq_offset=row["qfq_offset"],
                hfq_multiplier=row["hfq_multiplier"], hfq_offset=row["hfq_offset"],
                action_hash=row["action_hash"], algorithm_version=row["algorithm_version"],
                source=row["source"], calculated_at=datetime.fromisoformat(row["calculated_at"]),
            )
            for row in rows
        ]

    def query(
        self,
        *,
        market: str | None = None,
        instrument_type: str | None = None,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        codes: list[str] | None = None,
        page: int = 1,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> MarketDailyBarPage:
        clauses: list[str] = []
        parameters: list[object] = []
        if market:
            clauses.append("market=?")
            parameters.append(market)
        if instrument_type:
            clauses.append("instrument_type=?")
            parameters.append(instrument_type)
        if codes:
            placeholders = ",".join("?" for _ in codes)
            clauses.append(f"code IN ({placeholders})")
            parameters.extend(codes)
        range_query = start_date is not None and end_date is not None
        if trade_date is None and not range_query:
            latest_clauses = list(clauses)
            latest_parameters = list(parameters)
            latest_where = f"WHERE {' AND '.join(latest_clauses)}" if latest_clauses else ""
            with self._connect() as connection:
                latest = connection.execute(
                    f"SELECT MAX(trade_date) AS trade_date FROM market_daily_bars {latest_where}",  # noqa: S608
                    latest_parameters,
                ).fetchone()["trade_date"]
            trade_date = date.fromisoformat(latest) if latest else None
        if trade_date is not None:
            clauses.append("trade_date=?")
            parameters.append(trade_date.isoformat())
        elif start_date is not None and end_date is not None:
            clauses.extend(("trade_date>=?", "trade_date<=?"))
            parameters.extend((start_date.isoformat(), end_date.isoformat()))
        count_clauses = list(clauses)
        count_parameters = list(parameters)
        if cursor:
            cursor_date, cursor_market, cursor_type, cursor_code, cursor_adjustment = (
                _decode_page_cursor(cursor)
            )
            clauses.append(
                "(trade_date < ? OR (trade_date = ? AND "
                "(market, instrument_type, code, adjustment) > (?, ?, ?, ?)))"
            )
            parameters.extend((
                cursor_date, cursor_date, cursor_market, cursor_type, cursor_code,
                cursor_adjustment,
            ))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        count_where = f"WHERE {' AND '.join(count_clauses)}" if count_clauses else ""
        offset = 0 if cursor else (page - 1) * page_size
        with self._connect() as connection:
            total = int(connection.execute(
                f"SELECT COUNT(*) AS total FROM market_daily_bars {count_where}",  # noqa: S608
                count_parameters,
            ).fetchone()["total"])
            rows = connection.execute(
                f"""
                SELECT * FROM market_daily_bars {where}
                ORDER BY trade_date DESC, market, instrument_type, code, adjustment LIMIT ? OFFSET ?
                """,  # noqa: S608
                [*parameters, page_size + 1, offset],
            ).fetchall()
        has_more = len(rows) > page_size
        visible_rows = rows[:page_size]
        next_cursor = _encode_page_cursor(visible_rows[-1]) if has_more and visible_rows else None
        return MarketDailyBarPage(
            items=[_row_to_price(row) for row in visible_rows],
            total=total,
            page=page,
            page_size=page_size,
            trade_date=trade_date,
            start_date=start_date if range_query else None,
            end_date=end_date if range_query else None,
            next_cursor=next_cursor,
        )
