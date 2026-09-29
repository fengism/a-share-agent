from __future__ import annotations

import json
import sqlite3
from collections import Counter
from collections.abc import Iterable
from typing import Any

from app.infrastructure.persistence.concept_stats import apply_concept_deltas, concept_delta, rebuild_concept_counts
from app.infrastructure.persistence.connection import get_connection, unit_of_work
from app.modules.master_data_revision import check_revision, record_revision
from app.modules.stock_concept.models import StockConceptRecordInput


class ImportBatchStateChangedError(RuntimeError):
    pass


def _connection() -> sqlite3.Connection:
    return get_connection("industry")


def _record(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["revision"] = record_revision(result)
    result["is_manual_override"] = bool(result["is_manual_override"])
    raw_concepts = result.get("concepts_json")
    if isinstance(raw_concepts, str):
        try:
            result["concepts"] = json.loads(raw_concepts)
        except Exception:
            result["concepts"] = []
    elif isinstance(raw_concepts, list):
        result["concepts"] = raw_concepts
    else:
        result["concepts"] = []
    result.pop("concepts_json", None)
    return result


def list_records(
    *,
    query: str = "",
    market_group: str = "",
    concept: str = "",
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    where: list[str] = []
    params: list[object] = []
    if query:
        normalized = query.strip().upper()
        where.append("(stock_code LIKE ? OR stock_name LIKE ?)")
        params.extend((f"{normalized}%", f"%{query.strip()}%"))
    if market_group:
        where.append("market_group = ?")
        params.append(market_group)
    if concept:
        where.append("""EXISTS (
            SELECT 1 FROM json_each(CASE WHEN json_valid(concepts_json) THEN concepts_json ELSE '[]' END)
            WHERE type='text' AND value = ?
        )""")
        params.append(concept.strip())

    clause = f" WHERE {' AND '.join(where)}" if where else ""
    connection = _connection()
    total = int(
        connection.execute(
            f"SELECT COUNT(*) FROM stock_concept_mappings{clause}", params
        ).fetchone()[0]
    )
    if page_size and page_size > 0:
        rows = connection.execute(
            f"""
            SELECT * FROM stock_concept_mappings{clause}
            ORDER BY market_group, stock_code
            LIMIT ? OFFSET ?
            """,
            (*params, page_size, (page - 1) * page_size),
        ).fetchall()
    else:
        rows = connection.execute(
            f"""
            SELECT * FROM stock_concept_mappings{clause}
            ORDER BY market_group, stock_code
            """,
            params,
        ).fetchall()
    return [_record(row) for row in rows], total


def get_record(stock_code: str) -> dict[str, Any] | None:
    code = stock_code.strip().upper()
    conn = _connection()
    row = conn.execute(
        "SELECT * FROM stock_concept_mappings WHERE stock_code = ?",
        (code,),
    ).fetchone()
    if not row and "." not in code:
        row = conn.execute(
            "SELECT * FROM stock_concept_mappings WHERE stock_code LIKE ?",
            (f"{code}.%",),
        ).fetchone()
    return _record(row) if row else None


def get_record_by_id(record_id: int) -> dict[str, Any] | None:
    row = _connection().execute(
        "SELECT * FROM stock_concept_mappings WHERE id = ?", (record_id,)
    ).fetchone()
    return _record(row) if row else None


def _manual_values(record: StockConceptRecordInput) -> tuple[object, ...]:
    concepts_json = json.dumps(record.concepts, ensure_ascii=False)
    return (
        record.market_group,
        record.exchange_suffix,
        record.stock_code,
        record.stock_name,
        concepts_json,
        record.source_version,
    )


def create_manual(record: StockConceptRecordInput) -> int:
    with unit_of_work(connection=_connection(), immediate=True) as work:
        cursor = work.connection.execute(
            """
            INSERT INTO stock_concept_mappings(
                market_group, exchange_suffix, stock_code, stock_name,
                concepts_json, source, source_version, is_manual_override
            ) VALUES (?, ?, ?, ?, ?, 'manual', ?, 1)
            """,
            _manual_values(record),
        )
        record_id = int(cursor.lastrowid)
        apply_concept_deltas(work.connection, concept_delta([], record.concepts))
        return record_id


def update_manual(record_id: int, record: StockConceptRecordInput, *, expected_revision: str | None = None) -> bool:
    with unit_of_work(connection=_connection(), immediate=True) as work:
        current = work.connection.execute("SELECT * FROM stock_concept_mappings WHERE id=?", (record_id,)).fetchone()
        if expected_revision is not None:
            check_revision(current, expected_revision)
        if current is None:
            return False
        cursor = work.connection.execute(
            """
            UPDATE stock_concept_mappings SET
                market_group=?, exchange_suffix=?, stock_code=?, stock_name=?,
                concepts_json=?, source='manual', source_version=?, is_manual_override=1,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (*_manual_values(record), record_id),
        )
        success = cursor.rowcount > 0
        if success:
            apply_concept_deltas(work.connection, concept_delta(current["concepts_json"], record.concepts))
        return success


def delete_record(record_id: int) -> bool:
    with unit_of_work(connection=_connection(), immediate=True) as work:
        current = work.connection.execute(
            "SELECT concepts_json FROM stock_concept_mappings WHERE id=?", (record_id,)
        ).fetchone()
        if current is None:
            return False
        work.connection.execute("DELETE FROM stock_concept_mappings WHERE id=?", (record_id,))
        apply_concept_deltas(work.connection, concept_delta(current["concepts_json"], []))
        return True


def get_all_concepts(query: str = "", limit: int = 500) -> list[dict[str, Any]]:
    connection = _connection()
    if query:
        rows = connection.execute(
            """
            SELECT name, stock_count FROM stock_concepts
            WHERE name LIKE ?
            ORDER BY stock_count DESC, name ASC
            LIMIT ?
            """,
            (f"%{query.strip()}%", limit),
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT name, stock_count FROM stock_concepts
            ORDER BY stock_count DESC, name ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [{"name": str(row[0]), "stock_count": int(row[1])} for row in rows]


def stats() -> dict[str, Any]:
    connection = _connection()
    total_stocks = int(
        connection.execute("SELECT COUNT(*) FROM stock_concept_mappings").fetchone()[0]
    )
    total_concepts = int(
        connection.execute("SELECT COUNT(*) FROM stock_concepts").fetchone()[0]
    )
    latest_updated_at_row = connection.execute(
        "SELECT MAX(updated_at) FROM stock_concept_mappings"
    ).fetchone()
    latest_updated_at = str(latest_updated_at_row[0]) if latest_updated_at_row and latest_updated_at_row[0] else None

    market_counts = {"A": 0, "HK": 0, "OVERSEAS": 0}
    for row in connection.execute(
        "SELECT market_group, COUNT(*) FROM stock_concept_mappings GROUP BY market_group"
    ).fetchall():
        market_counts[str(row[0])] = int(row[1])

    return {
        "total_stocks": total_stocks,
        "total_concepts": total_concepts,
        "market_counts": market_counts,
        "latest_updated_at": latest_updated_at,
    }


def _existing_by_codes(
    connection: sqlite3.Connection, codes: Iterable[str]
) -> dict[str, dict[str, Any]]:
    raw_list = list(dict.fromkeys(code.strip().upper() for code in codes if code))
    if not raw_list:
        return {}
    expanded: set[str] = set(raw_list)
    for c in raw_list:
        if "." not in c:
            for suffix in ("SZ", "SH", "BJ"):
                expanded.add(f"{c}.{suffix}")
    code_list = list(expanded)
    result: dict[str, dict[str, Any]] = {}
    for start in range(0, len(code_list), 800):
        batch = code_list[start : start + 800]
        placeholders = ",".join("?" for _ in batch)
        rows = connection.execute(
            f"SELECT * FROM stock_concept_mappings WHERE stock_code IN ({placeholders})",
            batch,
        ).fetchall()
        for row in rows:
            rec = _record(row)
            stock_code = str(rec["stock_code"])
            result[stock_code] = rec
            bare = stock_code.split(".", 1)[0]
            if bare not in result:
                result[bare] = rec
    return result


def existing_by_codes(codes: Iterable[str]) -> dict[str, dict[str, Any]]:
    return _existing_by_codes(_connection(), codes)


def get_concepts_for_codes(codes: Iterable[str]) -> dict[str, list[str]]:
    existing = existing_by_codes(codes)
    return {code: data.get("concepts", []) for code, data in existing.items()}


def rebuild_stock_concepts(connection: sqlite3.Connection) -> None:
    """仅用于初始化/修复，普通写入使用增量计数。"""
    rebuild_concept_counts(connection)


def classify_import_records(
    records: list[dict[str, Any]], *, force_override: bool = False
) -> dict[str, int]:
    counts = {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    existing = existing_by_codes(str(record["stock_code"]) for record in records)
    for record in records:
        stock_code = str(record["stock_code"])
        current = existing.get(stock_code)
        incoming_concepts = sorted(set(record.get("concepts") or []))
        if current and current["is_manual_override"] and not force_override:
            counts["skipped"] += 1
        elif current and sorted(current.get("concepts") or []) == incoming_concepts and current.get("stock_name") == record.get("stock_name"):
            counts["unchanged"] += 1
        elif current:
            counts["updated"] += 1
        else:
            counts["added"] += 1
    return counts


def upsert_import_records(
    records: list[dict[str, Any]],
    *,
    source_version: str,
    force_override: bool,
) -> dict[str, int]:
    counts = {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    deltas: Counter[str] = Counter()
    connection = _connection()
    with unit_of_work(connection=connection, immediate=True) as work:
        existing = _existing_by_codes(work.connection, (str(record["stock_code"]) for record in records))
        for record in records:
            stock_code = str(record["stock_code"])
            current = existing.get(stock_code)
            incoming_concepts = sorted(set(record.get("concepts") or []))
            concepts_json = json.dumps(incoming_concepts, ensure_ascii=False)
            if current and current["is_manual_override"] and not force_override:
                counts["skipped"] += 1
                continue
            if current and sorted(current.get("concepts") or []) == incoming_concepts and current.get("stock_name") == record.get("stock_name"):
                counts["unchanged"] += 1
                continue
            work.connection.execute(
                """
                INSERT INTO stock_concept_mappings(
                    market_group, exchange_suffix, stock_code, stock_name,
                    concepts_json, source, source_version, is_manual_override
                ) VALUES (?, ?, ?, ?, ?, 'csv', ?, 0)
                ON CONFLICT(stock_code) DO UPDATE SET
                    market_group=excluded.market_group,
                    exchange_suffix=excluded.exchange_suffix,
                    stock_name=excluded.stock_name,
                    concepts_json=excluded.concepts_json,
                    source='csv',
                    source_version=excluded.source_version,
                    is_manual_override=0,
                    updated_at=datetime('now','localtime')
                """,
                (
                    record.get("market_group", "A"),
                    record.get("exchange_suffix", "SZ"),
                    stock_code,
                    record.get("stock_name", ""),
                    concepts_json,
                    source_version,
                ),
            )
            deltas.update(concept_delta(current.get("concepts", []) if current else [], incoming_concepts))
            existing[stock_code] = {**record, "concepts": incoming_concepts, "is_manual_override": False}
            counts["updated" if current else "added"] += 1

        apply_concept_deltas(work.connection, deltas)
    return counts


def save_import_batch(
    *,
    token: str,
    content_hash: str,
    filename: str,
    source_version: str,
    status: str,
    summary: dict[str, int],
    warnings: list[str],
) -> None:
    connection = _connection()
    with unit_of_work(connection=connection, immediate=True) as work:
        work.connection.execute(
            """
            INSERT INTO stock_concept_import_batches(
                import_token, content_hash, filename, source_version, status,
                total_rows, valid_rows, added_rows, updated_rows, unchanged_rows,
                skipped_rows, invalid_rows, warnings_json, committed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      CASE WHEN ?='committed' THEN datetime('now','localtime') ELSE NULL END)
            ON CONFLICT(import_token) DO UPDATE SET
                status=excluded.status, added_rows=excluded.added_rows,
                updated_rows=excluded.updated_rows, unchanged_rows=excluded.unchanged_rows,
                skipped_rows=excluded.skipped_rows, invalid_rows=excluded.invalid_rows,
                warnings_json=excluded.warnings_json,
                committed_at=CASE WHEN excluded.status='committed' THEN datetime('now','localtime') ELSE committed_at END
            """,
            (
                token,
                content_hash,
                filename,
                source_version,
                status,
                summary.get("total_rows", 0),
                summary.get("valid_rows", 0),
                summary.get("added_rows", 0),
                summary.get("updated_rows", 0),
                summary.get("unchanged_rows", 0),
                summary.get("skipped_rows", 0),
                summary.get("invalid_rows", 0),
                json.dumps(warnings, ensure_ascii=False),
                status,
            ),
        )


def get_import_batch(token: str) -> dict[str, Any] | None:
    row = _connection().execute(
        "SELECT * FROM stock_concept_import_batches WHERE import_token = ?", (token,)
    ).fetchone()
    if not row:
        return None
    result = dict(row)
    try:
        result["warnings"] = json.loads(str(result.get("warnings_json") or "[]"))
    except Exception:
        result["warnings"] = []
    return result


def commit_import_batch(
    *,
    token: str,
    records: list[dict[str, Any]],
    source_version: str,
    force_override: bool,
) -> dict[str, int]:
    connection = _connection()
    with unit_of_work(connection=connection, immediate=True) as work:
        current = work.connection.execute(
            "SELECT status FROM stock_concept_import_batches WHERE import_token=?", (token,)
        ).fetchone()
        if current is None or current["status"] != "previewed":
            raise ImportBatchStateChangedError("导入批次状态已变化，请重新预检")
        # upsert 的嵌套 unit_of_work 使用 SAVEPOINT；数据、派生统计、批次共同提交。
        counts = upsert_import_records(
            records,
            source_version=source_version,
            force_override=force_override,
        )
        work.connection.execute(
            """
            UPDATE stock_concept_import_batches SET
                status='committed',
                added_rows=?,
                updated_rows=?,
                unchanged_rows=?,
                skipped_rows=?,
                committed_at=datetime('now','localtime')
            WHERE import_token=?
            """,
            (
                counts["added"],
                counts["updated"],
                counts["unchanged"],
                counts["skipped"],
                token,
            ),
        )
    return counts


def a_share_all_concepts_mapping() -> dict[str, list[str]]:
    """返回全市场 A 股概念列表映射：{code: [concept, ...]}"""
    rows = _connection().execute(
        "SELECT stock_code, concepts_json FROM stock_concept_mappings WHERE market_group='A'"
    ).fetchall()
    result: dict[str, list[str]] = {}
    for row in rows:
        raw_code = str(row["stock_code"]).strip()
        bare_code = raw_code.split(".", 1)[0]
        raw_concepts = row["concepts_json"]
        concepts: list[str] = []
        if isinstance(raw_concepts, str):
            try:
                parsed = json.loads(raw_concepts)
                if isinstance(parsed, list):
                    concepts = [str(c).strip() for c in parsed if str(c).strip()]
            except Exception:
                pass
        elif isinstance(raw_concepts, list):
            concepts = [str(c).strip() for c in raw_concepts if str(c).strip()]
        result[bare_code] = concepts
        result[raw_code] = concepts
    return result

