"""国家队 ETF 份额与回填状态的 SQLite 持久化。

将历史 JSON 快照（shares.json）替换为 market_data.db 中两张关系表：
- national_team_etf_shares: (code, date) -> shares，支持按点增量 upsert。
- national_team_etf_backfill_state: (scope, date) 记录已检查的回填交易日。
"""

from __future__ import annotations

import json
import math
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Iterable

from app.core.market import market_today
from app.infrastructure.persistence.connection import get_connection, unit_of_work

ALL_ETFS = "all"

_SHARES_UPSERT = """
INSERT INTO national_team_etf_shares(code, date, shares, updated_at, source, verification_status)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(code, date) DO UPDATE SET
    shares      = excluded.shares,
    updated_at  = excluded.updated_at,
    source = excluded.source,
    verification_status = excluded.verification_status
WHERE national_team_etf_shares.verification_status != 'verified'
   OR excluded.verification_status = 'verified'
"""

_BACKFILL_UPSERT = """
INSERT INTO national_team_etf_backfill_state(scope, date, updated_at)
VALUES (?, ?, ?)
ON CONFLICT(scope, date) DO UPDATE SET
    updated_at = excluded.updated_at
"""


def load_share_history(codes: Iterable[str], *, verified_only: bool = False) -> dict[str, dict[str, float]]:
    """加载指定 ETF 的全部存量份额历史。

    Returns:
        {code: {date: shares}}。
    """
    code_list = list(dict.fromkeys(codes))
    if not code_list:
        return {}
    placeholders = ",".join("?" for _ in code_list)
    rows = (
        get_connection("market")
        .execute(
            f"SELECT code, date, shares FROM national_team_etf_shares "
            f"WHERE code IN ({placeholders}) "
            + ("AND verification_status = 'verified' " if verified_only else "")
            + "ORDER BY code, date",
            code_list,
        )
        .fetchall()
    )
    history: dict[str, dict[str, float]] = {}
    for row in rows:
        history.setdefault(row["code"], {})[row["date"]] = float(row["shares"])
    return history


def save_shares(
    samples: Iterable[tuple[str, str, float]], *, source: str = "unknown", verification_status: str = "unknown"
) -> None:
    """校验整批后 upsert；未核验样本不可覆盖已核验记录。

    Args:
        samples: (code, date, shares) 的迭代序列。
    """
    now = _now()
    rows = [
        (
            code,
            _validated_date(point_date),
            _nonnegative_finite(shares, field=f"shares ({code}, {point_date})"),
            now,
            source,
            verification_status,
        )
        for code, point_date, shares in samples
    ]
    if not rows:
        return
    with unit_of_work() as work:
        work.connection.executemany(_SHARES_UPSERT, rows)


def load_checked_dates(scope: str = ALL_ETFS) -> set[str]:
    """读取指定回填作用域已检查的日期集合。"""
    rows = (
        get_connection("market")
        .execute(
            "SELECT date FROM national_team_etf_backfill_state WHERE scope = ?",
            (scope,),
        )
        .fetchall()
    )
    return {row["date"] for row in rows}


def mark_checked_dates(scope: str, dates: Iterable[str]) -> None:
    """写入指定作用域已检查的日期（幂等 upsert）。"""
    now = _now()
    rows = [(scope, _validated_date(point_date), now) for point_date in dates]
    if not rows:
        return
    with unit_of_work() as work:
        work.connection.executemany(_BACKFILL_UPSERT, rows)


def save_snapshot(
    samples_by_source: dict[str, Iterable[tuple[str, str, float]]],
    checked_sse_dates: Iterable[str],
    checked_szse_dates: Iterable[str],
) -> None:
    """原子保存官方历史增量与回填状态，失败时整批回滚。"""
    with unit_of_work():
        # 内层写入复用同一线程连接的 savepoint，不提前提交外层事务。
        for source, samples in samples_by_source.items():
            save_shares(samples, source=source, verification_status="verified")
        mark_checked_dates("sse", checked_sse_dates)
        mark_checked_dates("szse", checked_szse_dates)
        prune(retention_days=370)


def import_legacy_snapshot(
    path: Path,
    *,
    allowed_codes: Iterable[str] | None = None,
) -> bool:
    """将旧 JSON 快照一次性导入 SQLite，幂等可重复调用。

    Args:
        path: 旧 shares.json 路径。
        allowed_codes: 只导入这些代码，默认导入全部。

    Returns:
        是否导入了数据。
    """
    marker = str(path.resolve())
    conn = get_connection("market")
    if conn.execute("SELECT 1 FROM national_team_etf_imports WHERE path = ?", (marker,)).fetchone():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return False
    if not isinstance(payload, dict) or not isinstance(payload.get("series"), dict):
        return False
    allowed = set(allowed_codes) if allowed_codes is not None else None
    now = _now()
    samples = []
    for code, values in payload["series"].items():
        if (allowed is not None and code not in allowed) or not isinstance(values, dict):
            continue
        for point_date, value in values.items():
            try:
                if date.fromisoformat(point_date).isoformat() != point_date:
                    continue
                shares = float(value)
                if isinstance(value, bool) or not math.isfinite(shares) or shares < 0:
                    continue
                samples.append((code, point_date, shares, now, "legacy_json", "unknown"))
            except (TypeError, ValueError):
                continue
    with unit_of_work(immediate=True) as work:
        # 数据、回填状态与导入标记同事务；并发导入也不可覆盖正式记录。
        if work.connection.execute("SELECT 1 FROM national_team_etf_imports WHERE path = ?", (marker,)).fetchone():
            return False
        work.connection.executemany(
            "INSERT INTO national_team_etf_shares(code, date, shares, updated_at, source, verification_status) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(code, date) DO NOTHING",
            samples,
        )
        for scope, key in (("sse", "checked_sse_dates"), ("szse", "checked_szse_dates")):
            raw_dates = payload.get(key, [])
            valid_dates = []
            for value in raw_dates if isinstance(raw_dates, list) else []:
                try:
                    if date.fromisoformat(value).isoformat() == value:
                        valid_dates.append((scope, value, now))
                except (TypeError, ValueError):
                    continue
            work.connection.executemany(
                "INSERT INTO national_team_etf_backfill_state(scope, date, updated_at) "
                "VALUES (?, ?, ?) ON CONFLICT(scope, date) DO NOTHING",
                valid_dates,
            )
        work.connection.execute("INSERT INTO national_team_etf_imports(path, imported_at) VALUES (?, ?)", (marker, now))
    return bool(samples)


def load_share_metadata(codes: Iterable[str]) -> dict[str, dict[str, dict]]:
    codes = list(codes)
    if not codes:
        return {}
    placeholders = ",".join("?" for _ in codes)
    rows = get_connection("market").execute(
        f"SELECT code, date, source, verification_status, updated_at FROM national_team_etf_shares WHERE code IN ({placeholders})",
        codes,
    )
    result: dict[str, dict[str, dict]] = {}
    for row in rows:
        result.setdefault(row["code"], {})[row["date"]] = {
            "source": row["source"],
            "verification_status": row["verification_status"],
            "fetched_at": datetime.fromtimestamp(row["updated_at"], UTC).isoformat(timespec="seconds"),
        }
    return result


def save_observations(samples: Iterable[tuple[str, str, float, float]]) -> None:
    rows = [
        (
            code,
            source,
            _nonnegative_finite(shares, field=f"shares ({code}, {source})"),
            _nonnegative_finite(fetched_at, field=f"fetched_at ({code}, {source})"),
        )
        for code, source, shares, fetched_at in samples
    ]
    if not rows:
        return
    with unit_of_work() as work:
        work.connection.executemany(
            "INSERT INTO national_team_etf_observations(code, source, shares, fetched_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(code, source) DO UPDATE SET shares=excluded.shares, fetched_at=excluded.fetched_at "
            "WHERE excluded.fetched_at >= national_team_etf_observations.fetched_at",
            rows,
        )


def load_observations(codes: Iterable[str]) -> list[dict]:
    codes = list(codes)
    if not codes:
        return []
    placeholders = ",".join("?" for _ in codes)
    rows = get_connection("market").execute(
        f"SELECT * FROM national_team_etf_observations WHERE code IN ({placeholders}) ORDER BY code, source",
        codes,
    )
    return [dict(row) for row in rows]


def prune(retention_days: int = 370) -> None:
    """清理超过保留期的份额与回填状态（按数据日期裁剪）。"""
    cutoff = (market_today() - timedelta(days=retention_days)).isoformat()
    with unit_of_work() as work:
        work.connection.execute("DELETE FROM national_team_etf_shares WHERE date < ?", (cutoff,))
        work.connection.execute("DELETE FROM national_team_etf_backfill_state WHERE date < ?", (cutoff,))
        work.connection.execute(
            "DELETE FROM national_team_etf_observations WHERE fetched_at < ?", (_now() - 7 * 86400,)
        )


def _now() -> float:
    """当前时间戳（秒，与库内其他 REAL 时间列保持一致）。"""
    return time.time()


def _validated_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid date: {value!r}; expected YYYY-MM-DD") from error
    if parsed.isoformat() != value:
        raise ValueError(f"invalid date: {value!r}; expected YYYY-MM-DD")
    return value


def _nonnegative_finite(value: float, *, field: str) -> float:
    message = f"invalid {field}: {value!r}; expected a finite non-negative number"
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(message) from error
    if isinstance(value, bool) or not math.isfinite(number) or number < 0:
        raise ValueError(message)
    return number
