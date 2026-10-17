from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping
from typing import Any

from app.infrastructure.persistence.connection import get_connection, unit_of_work
from app.infrastructure.persistence.master_data_repair import backfill_industry_stock_names
from app.modules.industry_classification.models import IndustryRecordInput
from app.modules.master_data_revision import check_revision, record_revision

_PROVIDER = "sina_akshare"
_RECORD_FIELDS = (
    "market_group",
    "exchange_suffix",
    "stock_name",
    "sw_level1_name",
    "sw_level2_name",
    "sw_level3_name",
    "sw_industry_code",
)
_REFRESH_FIELDS = {
    "enabled",
    "interval_seconds",
    "last_started_at",
    "last_succeeded_at",
    "last_failed_at",
    "last_error",
    "last_added",
    "last_updated",
    "last_unchanged",
}


class ImportBatchStateChangedError(RuntimeError):
    pass


class IndustryRecordConflictError(RuntimeError):
    """手工写入违反唯一约束（如股票代码重复）。

    存储层的 ``sqlite3.IntegrityError`` 在数据访问层就翻译成领域错误，
    以免 API 层依赖具体数据库实现。
    """


def _connection() -> sqlite3.Connection:
    return get_connection("industry")


def _record(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["revision"] = record_revision(result)
    result["is_manual_override"] = bool(result["is_manual_override"])
    return result


def list_records(
    *,
    query: str = "",
    market_group: str = "",
    level1: str = "",
    level2: str = "",
    level3: str = "",
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    where: list[str] = []
    params: list[object] = []
    if query:
        normalized = query.strip().upper()
        where.append("(stock_code LIKE ? OR stock_name LIKE ?)")
        params.extend((f"{normalized}%", f"%{query.strip()}%"))
    for column, value in (
        ("market_group", market_group),
        ("sw_level1_name", level1),
        ("sw_level2_name", level2),
        ("sw_level3_name", level3),
    ):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    connection = _connection()
    total = int(
        connection.execute(
            f"SELECT COUNT(*) FROM sw_industry_classifications{clause}", params
        ).fetchone()[0]
    )
    if page_size and page_size > 0:
        rows = connection.execute(
            f"""
            SELECT * FROM sw_industry_classifications{clause}
            ORDER BY market_group, stock_code
            LIMIT ? OFFSET ?
            """,
            (*params, page_size, (page - 1) * page_size),
        ).fetchall()
    else:
        rows = connection.execute(
            f"""
            SELECT * FROM sw_industry_classifications{clause}
            ORDER BY market_group, stock_code
            """,
            params,
        ).fetchall()
    return [_record(row) for row in rows], total


def get_record(stock_code: str) -> dict[str, Any] | None:
    code = stock_code.strip().upper()
    conn = _connection()
    row = conn.execute(
        "SELECT * FROM sw_industry_classifications WHERE stock_code = ?",
        (code,),
    ).fetchone()
    if not row and "." not in code:
        row = conn.execute(
            "SELECT * FROM sw_industry_classifications WHERE stock_code LIKE ?",
            (f"{code}.%",),
        ).fetchone()
    return _record(row) if row else None


def get_records_by_stock_codes(stock_codes: Iterable[str]) -> dict[str, dict[str, Any]]:
    """批量读取股票行业，避免组合风险计算逐只查询数据库。"""
    normalized = {str(code).strip().upper() for code in stock_codes if str(code).strip()}
    if not normalized:
        return {}
    aliases = normalized | {code.split(".", 1)[0] for code in normalized}
    placeholders = ",".join("?" for _ in aliases)
    rows = _connection().execute(
        f"""
        SELECT * FROM sw_industry_classifications
        WHERE stock_code IN ({placeholders})
           OR CASE WHEN instr(stock_code, '.') > 0
                   THEN substr(stock_code, 1, instr(stock_code, '.') - 1)
                   ELSE stock_code END IN ({placeholders})
        """,
        (*aliases, *aliases),
    ).fetchall()
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        record = _record(row)
        raw_code = str(record["stock_code"]).strip().upper()
        result[raw_code] = record
        result.setdefault(raw_code.split(".", 1)[0], record)
    return {
        code: result.get(code) or result.get(code.split(".", 1)[0])
        for code in normalized
        if result.get(code) or result.get(code.split(".", 1)[0])
    }


def get_record_by_id(record_id: int) -> dict[str, Any] | None:
    row = _connection().execute(
        "SELECT * FROM sw_industry_classifications WHERE id = ?", (record_id,)
    ).fetchone()
    return _record(row) if row else None


def _manual_values(record: IndustryRecordInput) -> tuple[object, ...]:
    values = record.model_dump(mode="json")
    return tuple(
        values[key]
        for key in (
            "market_group",
            "exchange_suffix",
            "stock_code",
            "stock_name",
            "sw_level1_name",
            "sw_level2_name",
            "sw_level3_name",
            "sw_industry_code",
            "source_version",
            "effective_date",
        )
    )


def create_manual(record: IndustryRecordInput) -> int:
    try:
        with unit_of_work(connection=_connection(), immediate=True) as work:
            cursor = work.connection.execute(
                """
                INSERT INTO sw_industry_classifications(
                    market_group, exchange_suffix, stock_code, stock_name,
                    sw_level1_name, sw_level2_name, sw_level3_name, sw_industry_code,
                    source, source_version, effective_date, is_manual_override
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?, 1)
                """,
                _manual_values(record),
            )
            return int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise IndustryRecordConflictError("股票代码已存在") from exc


def update_manual(record_id: int, record: IndustryRecordInput, *, expected_revision: str | None = None) -> bool:
    try:
        with unit_of_work(connection=_connection(), immediate=True) as work:
            if expected_revision is not None:
                current = work.connection.execute("SELECT * FROM sw_industry_classifications WHERE id=?", (record_id,)).fetchone()
                check_revision(current, expected_revision)
            cursor = work.connection.execute(
                """
                UPDATE sw_industry_classifications SET
                    market_group=?, exchange_suffix=?, stock_code=?, stock_name=?,
                    sw_level1_name=?, sw_level2_name=?, sw_level3_name=?, sw_industry_code=?,
                    source='manual', source_version=?, effective_date=?, is_manual_override=1,
                    updated_at=datetime('now','localtime')
                WHERE id=?
                """,
                (*_manual_values(record), record_id),
            )
            return cursor.rowcount > 0
    except sqlite3.IntegrityError as exc:
        raise IndustryRecordConflictError("股票代码已存在") from exc


def delete_record(record_id: int) -> bool:
    with unit_of_work(connection=_connection(), immediate=True) as work:
        return (
            work.connection.execute(
                "DELETE FROM sw_industry_classifications WHERE id = ?", (record_id,)
            ).rowcount
            > 0
        )


def hierarchy(
    *, market_group: str = "", level1: str = "", level2: str = ""
) -> dict[str, list[str]]:
    connection = _connection()

    def distinct(column: str, filters: list[tuple[str, str]]) -> list[str]:
        clauses = [f"{column} <> ''"]
        params: list[str] = []
        for name, value in filters:
            if value:
                clauses.append(f"{name} = ?")
                params.append(value)
        rows = connection.execute(
            f"SELECT DISTINCT {column} FROM sw_industry_classifications "
            f"WHERE {' AND '.join(clauses)} ORDER BY {column}",
            params,
        ).fetchall()
        return [str(row[0]) for row in rows]

    common = [("market_group", market_group)]
    return {
        "level1": distinct("sw_level1_name", common),
        "level2": distinct("sw_level2_name", [*common, ("sw_level1_name", level1)]),
        "level3": distinct(
            "sw_level3_name",
            [*common, ("sw_level1_name", level1), ("sw_level2_name", level2)],
        ),
    }


def stats() -> dict[str, Any]:
    connection = _connection()
    total_row = connection.execute(
        """
        SELECT COUNT(*) AS total,
               COUNT(DISTINCT NULLIF(sw_level1_name, '')) AS level1_count,
               COUNT(DISTINCT NULLIF(sw_level2_name, '')) AS level2_count,
               COUNT(DISTINCT NULLIF(sw_level3_name, '')) AS level3_count,
               MAX(updated_at) AS latest_updated_at
        FROM sw_industry_classifications
        """
    ).fetchone()
    market_counts = {"A": 0, "HK": 0, "OVERSEAS": 0}
    for row in connection.execute(
        "SELECT market_group, COUNT(*) FROM sw_industry_classifications GROUP BY market_group"
    ).fetchall():
        market_counts[str(row[0])] = int(row[1])
    return {**dict(total_row), "market_counts": market_counts}


def _existing_by_codes(
    connection: sqlite3.Connection, codes: Iterable[str]
) -> dict[str, dict[str, Any]]:
    code_list = list(dict.fromkeys(code.strip().upper() for code in codes if code))
    if not code_list:
        return {}
    result: dict[str, dict[str, Any]] = {}
    for start in range(0, len(code_list), 800):
        batch = code_list[start : start + 800]
        placeholders = ",".join("?" for _ in batch)
        rows = connection.execute(
            f"SELECT * FROM sw_industry_classifications WHERE stock_code IN ({placeholders})",
            batch,
        ).fetchall()
        result.update({str(row["stock_code"]): _record(row) for row in rows})
    return result


def existing_by_codes(codes: Iterable[str]) -> dict[str, dict[str, Any]]:
    return _existing_by_codes(_connection(), codes)


def records_equal(current: Mapping[str, Any], incoming: Mapping[str, Any]) -> bool:
    return all(
        str(current.get(key) or "") == str(incoming.get(key) or "")
        for key in _RECORD_FIELDS
    )


def classify_import_records(
    records: list[dict[str, Any]], *, force_override: bool = False
) -> dict[str, int]:
    counts = {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    existing = existing_by_codes(str(record["stock_code"]) for record in records)
    for record in records:
        current = existing.get(str(record["stock_code"]))
        if current and current["is_manual_override"] and not force_override:
            counts["skipped"] += 1
        elif current and records_equal(current, record):
            counts["unchanged"] += 1
        elif current:
            counts["updated"] += 1
        else:
            counts["added"] += 1
    return counts


def _upsert_import_records(
    connection: sqlite3.Connection,
    records: list[dict[str, Any]],
    *,
    source_version: str,
    effective_date: str | None,
    force_override: bool,
) -> dict[str, int]:
    counts = {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    existing = _existing_by_codes(connection, (str(record["stock_code"]) for record in records))
    for record in records:
        stock_code = str(record["stock_code"])
        current = existing.get(stock_code)
        if current and current["is_manual_override"] and not force_override:
            counts["skipped"] += 1
            continue
        if current and records_equal(current, record):
            counts["unchanged"] += 1
            continue
        connection.execute(
            """
            INSERT INTO sw_industry_classifications(
                market_group, exchange_suffix, stock_code, stock_name,
                sw_level1_name, sw_level2_name, sw_level3_name, sw_industry_code,
                source, source_version, effective_date, is_manual_override
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'excel', ?, ?, 0)
            ON CONFLICT(stock_code) DO UPDATE SET
                market_group=excluded.market_group,
                exchange_suffix=excluded.exchange_suffix,
                stock_name=excluded.stock_name,
                sw_level1_name=excluded.sw_level1_name,
                sw_level2_name=excluded.sw_level2_name,
                sw_level3_name=excluded.sw_level3_name,
                sw_industry_code=excluded.sw_industry_code,
                source='excel', source_version=excluded.source_version,
                effective_date=excluded.effective_date, is_manual_override=0,
                updated_at=datetime('now','localtime')
            """,
            (
                record["market_group"],
                record["exchange_suffix"],
                stock_code,
                record["stock_name"],
                record["sw_level1_name"],
                record["sw_level2_name"],
                record["sw_level3_name"],
                record["sw_industry_code"],
                source_version,
                effective_date,
            ),
        )
        counts["updated" if current else "added"] += 1
    return counts


def upsert_import_records(
    records: list[dict[str, Any]],
    *,
    source_version: str,
    effective_date: str | None,
    force_override: bool,
) -> dict[str, int]:
    with unit_of_work(connection=_connection(), immediate=True) as work:
        return _upsert_import_records(
            work.connection,
            records,
            source_version=source_version,
            effective_date=effective_date,
            force_override=force_override,
        )


def _normalize_a_share_code(raw_code: str) -> tuple[str, str]:
    base = str(raw_code).strip().upper().split(".", 1)[0].zfill(6)
    if base.startswith(("4", "8", "92")):
        suffix = "BJ"
    elif base.startswith(("5", "6", "9")):
        suffix = "SH"
    else:
        suffix = "SZ"
    return f"{base}.{suffix}", suffix


def upsert_a_share_mappings(mappings: dict[int, dict[str, str]]) -> dict[str, int]:
    normalized: dict[str, dict[int, str]] = {}
    for level, mapping in mappings.items():
        if level not in {1, 2, 3}:
            continue
        for raw_code, industry_name in mapping.items():
            name = str(industry_name or "").strip()
            if not name:
                continue
            stock_code, _ = _normalize_a_share_code(raw_code)
            normalized.setdefault(stock_code, {})[level] = name

    counts = {"added": 0, "updated": 0, "unchanged": 0}
    connection = _connection()
    with unit_of_work(connection=connection, immediate=True) as work:
        existing = _existing_by_codes(work.connection, normalized)
        for stock_code, levels in normalized.items():
            current = existing.get(stock_code)
            first = levels.get(1, "")
            second = levels.get(2, "")
            third = levels.get(3, "")
            if current and current["is_manual_override"]:
                counts["unchanged"] += 1
                continue
            if current:
                next_first = first or str(current["sw_level1_name"] or "")
                next_second = second or str(current["sw_level2_name"] or "")
                next_third = third or str(current["sw_level3_name"] or "")
                if (
                    next_first == str(current["sw_level1_name"] or "")
                    and next_second == str(current["sw_level2_name"] or "")
                    and next_third == str(current["sw_level3_name"] or "")
                ):
                    counts["unchanged"] += 1
                    continue
                work.connection.execute(
                    """
                    UPDATE sw_industry_classifications SET
                        sw_level1_name=?, sw_level2_name=?, sw_level3_name=?, source='sina_akshare',
                        updated_at=datetime('now','localtime')
                    WHERE id=?
                    """,
                    (next_first, next_second, next_third, current["id"]),
                )
                counts["updated"] += 1
            else:
                _, suffix = _normalize_a_share_code(stock_code)
                work.connection.execute(
                    """
                    INSERT INTO sw_industry_classifications(
                        market_group, exchange_suffix, stock_code, sw_level1_name,
                        sw_level2_name, sw_level3_name, source, is_manual_override
                    ) VALUES ('A', ?, ?, ?, ?, ?, 'sina_akshare', 0)
                    """,
                    (suffix, stock_code, first, second, third),
                )
                counts["added"] += 1
        backfill_industry_stock_names(work.connection)
    return counts


def _save_import_batch(
    connection: sqlite3.Connection,
    *,
    token: str,
    content_hash: str,
    filename: str,
    source_version: str,
    effective_date: str | None,
    status: str,
    summary: dict[str, int],
    warnings: list[str],
) -> None:
    connection.execute(
        """
        INSERT INTO sw_industry_import_batches(
            import_token, content_hash, filename, source_version, effective_date, status,
            total_rows, valid_rows, added_rows, updated_rows, unchanged_rows, skipped_rows,
            conflict_rows, invalid_rows, warnings_json, committed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  CASE WHEN ?='committed' THEN datetime('now','localtime') ELSE NULL END)
        ON CONFLICT(import_token) DO UPDATE SET
            status=excluded.status, added_rows=excluded.added_rows,
            updated_rows=excluded.updated_rows, unchanged_rows=excluded.unchanged_rows,
            skipped_rows=excluded.skipped_rows, conflict_rows=excluded.conflict_rows,
            invalid_rows=excluded.invalid_rows, warnings_json=excluded.warnings_json,
            committed_at=CASE WHEN excluded.status='committed'
                THEN datetime('now','localtime') ELSE sw_industry_import_batches.committed_at END
        """,
        (
            token,
            content_hash,
            filename,
            source_version,
            effective_date,
            status,
            summary["total_rows"],
            summary["valid_rows"],
            summary["added_rows"],
            summary["updated_rows"],
            summary["unchanged_rows"],
            summary["skipped_rows"],
            summary["conflict_rows"],
            summary["invalid_rows"],
            json.dumps(warnings, ensure_ascii=False),
            status,
        ),
    )


def save_import_batch(**values: Any) -> None:
    with unit_of_work(connection=_connection(), immediate=True) as work:
        _save_import_batch(work.connection, **values)


def commit_import_batch(
    *,
    token: str,
    records: list[dict[str, Any]],
    source_version: str,
    effective_date: str | None,
    force_override: bool,
    content_hash: str,
    filename: str,
    total_rows: int,
    conflict_rows: int,
    invalid_rows: int,
    warnings: list[str],
) -> dict[str, int]:
    connection = _connection()
    with unit_of_work(connection=connection, immediate=True) as work:
        current = work.connection.execute(
            "SELECT status FROM sw_industry_import_batches WHERE import_token=?", (token,)
        ).fetchone()
        if current is None or current["status"] != "previewed":
            raise ImportBatchStateChangedError("导入批次状态已变化，请重新预检")
        counts = _upsert_import_records(
            work.connection,
            records,
            source_version=source_version,
            effective_date=effective_date,
            force_override=force_override,
        )
        summary = {
            "total_rows": total_rows,
            "valid_rows": len(records),
            "added_rows": counts["added"],
            "updated_rows": counts["updated"],
            "unchanged_rows": counts["unchanged"],
            "skipped_rows": counts["skipped"],
            "conflict_rows": conflict_rows,
            "invalid_rows": invalid_rows,
        }
        _save_import_batch(
            work.connection,
            token=token,
            content_hash=content_hash,
            filename=filename,
            source_version=source_version,
            effective_date=effective_date,
            status="committed",
            summary=summary,
            warnings=warnings,
        )
        return counts


def get_import_batch(token: str) -> dict[str, Any] | None:
    row = _connection().execute(
        "SELECT * FROM sw_industry_import_batches WHERE import_token = ?", (token,)
    ).fetchone()
    return dict(row) if row else None


def get_refresh_state() -> dict[str, Any]:
    with unit_of_work(connection=_connection(), immediate=True) as work:
        work.connection.execute(
            "INSERT INTO sw_industry_refresh_state(provider) VALUES (?) "
            "ON CONFLICT(provider) DO NOTHING",
            (_PROVIDER,),
        )
    row = _connection().execute(
        "SELECT * FROM sw_industry_refresh_state WHERE provider = ?", (_PROVIDER,)
    ).fetchone()
    if row is None:
        raise RuntimeError("行业刷新状态初始化失败")
    result = dict(row)
    result["enabled"] = bool(result["enabled"])
    return result


def update_refresh_state(**fields: object) -> None:
    unknown = set(fields) - _REFRESH_FIELDS
    if unknown:
        raise ValueError(f"不支持的刷新状态字段: {', '.join(sorted(unknown))}")
    get_refresh_state()
    if not fields:
        return
    assignments = [f"{name}=?" for name in fields]
    params = list(fields.values())
    assignments.append("updated_at=datetime('now','localtime')")
    params.append(_PROVIDER)
    with unit_of_work(connection=_connection(), immediate=True) as work:
        work.connection.execute(
            f"UPDATE sw_industry_refresh_state SET {', '.join(assignments)} WHERE provider=?",
            params,
        )


def a_share_mapping(level: int) -> dict[str, str]:
    column = {1: "sw_level1_name", 2: "sw_level2_name", 3: "sw_level3_name"}.get(level)
    if column is None:
        raise ValueError(f"不支持的申万行业级别: {level}")
    rows = _connection().execute(
        f"SELECT stock_code, {column} FROM sw_industry_classifications "
        f"WHERE market_group='A' AND {column}<>''"
    ).fetchall()
    return {str(row["stock_code"]).split(".", 1)[0]: str(row[column]) for row in rows}


def a_share_all_levels_mapping() -> dict[str, dict[str, str]]:
    """返回全市场 A 股三级申万行业映射表：{code: {level1, level2, level3, code}}"""
    rows = _connection().execute(
        "SELECT stock_code, sw_level1_name, sw_level2_name, sw_level3_name, sw_industry_code "
        "FROM sw_industry_classifications WHERE market_group='A'"
    ).fetchall()
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        raw_code = str(row["stock_code"]).strip()
        bare_code = raw_code.split(".", 1)[0]
        data = {
            "level1": str(row["sw_level1_name"] or ""),
            "level2": str(row["sw_level2_name"] or ""),
            "level3": str(row["sw_level3_name"] or ""),
            "code": str(row["sw_industry_code"] or ""),
        }
        result[bare_code] = data
        result[raw_code] = data
    return result


def get_all_distinct_industries(level: int | None = None) -> list[str]:
    """返回申万行业名称列表，若指定级别则返回对应级别，否则返回全级别去重名称。"""
    conn = _connection()
    if level in (1, 2, 3):
        col = {1: "sw_level1_name", 2: "sw_level2_name", 3: "sw_level3_name"}[level]
        rows = conn.execute(
            f"SELECT DISTINCT {col} FROM sw_industry_classifications "
            f"WHERE market_group='A' AND {col}<>'' ORDER BY {col}"
        ).fetchall()
        return [str(r[0]) for r in rows if r[0]]

    rows = conn.execute(
        "SELECT DISTINCT sw_level1_name FROM sw_industry_classifications WHERE market_group='A' AND sw_level1_name<>'' "
        "UNION "
        "SELECT DISTINCT sw_level2_name FROM sw_industry_classifications WHERE market_group='A' AND sw_level2_name<>'' "
        "UNION "
        "SELECT DISTINCT sw_level3_name FROM sw_industry_classifications WHERE market_group='A' AND sw_level3_name<>''"
    ).fetchall()
    return sorted([str(r[0]) for r in rows if r[0]])
