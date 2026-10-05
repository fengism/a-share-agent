from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from typing import Any

from app.infrastructure.persistence.connection import get_connection, unit_of_work
from app.modules.master_data_revision import MasterDataConflictError, check_revision, record_revision
from app.modules.stock_profile.models import StockBasicProfileInput


def _connection() -> sqlite3.Connection:
    return get_connection("industry")


def _record(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["revision"] = record_revision(result)
    result["is_manual_override"] = bool(result["is_manual_override"])
    return result


_SW_FIELDS = ("sw_level1_name", "sw_level2_name", "sw_level3_name")


def _with_industries(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # 唯一权威来源为行业库；批量关联，避免逐行查询，也不回退到过期的历史副本。
    for start in range(0, len(records), 800):
        batch = records[start:start + 800]
        codes = [record["stock_code"] for record in batch]
        rows = _connection().execute(
            f"SELECT stock_code, {', '.join(_SW_FIELDS)} FROM sw_industry_classifications "
            f"WHERE stock_code IN ({','.join('?' for _ in codes)})", codes,
        ).fetchall()
        mapping = {row["stock_code"]: dict(row) for row in rows}
        for record in batch:
            industry = mapping.get(record["stock_code"], {})
            record.update({field: industry.get(field, "") for field in _SW_FIELDS})
    return records


def list_records(
    *,
    query: str = "",
    market_group: str = "",
    exchange: str = "",
    board: str = "",
    has_business: bool | None = None,
    has_listing_date: bool | None = None,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "stock_code",
    sort_order: str = "asc",
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

    if exchange:
        where.append("exchange = ?")
        params.append(exchange.upper())

    if board:
        where.append("board = ?")
        params.append(board)

    if has_business is True:
        where.append("main_business <> ''")
    elif has_business is False:
        where.append("main_business = ''")

    if has_listing_date is True:
        where.append("(listing_date IS NOT NULL AND listing_date <> '')")
    elif has_listing_date is False:
        where.append("(listing_date IS NULL OR listing_date = '')")

    clause = f" WHERE {' AND '.join(where)}" if where else ""

    allowed_sort_columns = {
        "stock_code": "stock_code",
        "listing_date": "listing_date",
        "updated_at": "updated_at",
        "stock_name": "stock_name",
        "board": "board",
    }
    col = allowed_sort_columns.get(sort_by, "stock_code")
    direction = "DESC" if sort_order.lower() == "desc" else "ASC"

    connection = _connection()
    total = int(
        connection.execute(
            f"SELECT COUNT(*) FROM stock_basic_profiles{clause}", params
        ).fetchone()[0]
    )

    if page_size and page_size > 0:
        rows = connection.execute(
            f"""
            SELECT * FROM stock_basic_profiles{clause}
            ORDER BY {col} {direction}
            LIMIT ? OFFSET ?
            """,
            (*params, page_size, (page - 1) * page_size),
        ).fetchall()
    else:
        rows = connection.execute(
            f"""
            SELECT * FROM stock_basic_profiles{clause}
            ORDER BY {col} {direction}
            """,
            params,
        ).fetchall()

    return _with_industries([_record(row) for row in rows]), total


def get_record(stock_code: str) -> dict[str, Any] | None:
    code = stock_code.strip().upper()
    conn = _connection()
    row = conn.execute(
        "SELECT * FROM stock_basic_profiles WHERE stock_code = ?",
        (code,),
    ).fetchone()
    if not row and "." not in code:
        row = conn.execute(
            "SELECT * FROM stock_basic_profiles WHERE stock_code LIKE ?",
            (f"{code}.%",),
        ).fetchone()
    return _with_industries([_record(row)])[0] if row else None


def get_record_by_id(record_id: int) -> dict[str, Any] | None:
    row = _connection().execute(
        "SELECT * FROM stock_basic_profiles WHERE id = ?", (record_id,)
    ).fetchone()
    return _with_industries([_record(row)])[0] if row else None


def _infer_a_share_board(raw_code: str, exchange: str) -> str:
    if raw_code.startswith("688"):
        return "科创板"
    if raw_code.startswith("30"):
        return "创业板"
    if raw_code.startswith(("4", "8", "920")):
        return "北交所"
    if exchange in {"SH", "SZ"}:
        return "主板"
    return ""


def ensure_basic_skeleton(
    *,
    stock_code: str,
    stock_name: str = "",
    market_group: str = "A",
    exchange: str = "",
    board: str = "",
    listing_date: str | None = None,
    industry: str = "",
    sw_level1_name: str = "",
    sw_level2_name: str = "",
    sw_level3_name: str = "",
    source: str = "auto_ensure",
) -> bool:
    """记录不存在时为该股创建一行最小档案；已存在（含手工维护）时不做任何修改。

    个股资料按需补全用：抓到主营/基础信息但库里还没有该股行时先建档，随后的
    ``update_business_info`` 才能把内容写进去。只落可长期复用的稳定身份字段，
    估值/概念等波动字段一律不落。
    """
    code = str(stock_code or "").strip().upper()
    if not code:
        return False
    raw_code = code.split(".", 1)[0]
    connection = _connection()
    # 无写锁快路径：绝大多数请求记录已存在，避免在只读路径上开写事务。
    existing = connection.execute(
        "SELECT 1 FROM stock_basic_profiles WHERE stock_code = ? OR stock_code = ? OR stock_code LIKE ?",
        (code, raw_code, f"{raw_code}.%"),
    ).fetchone()
    if existing is not None:
        return False
    resolved_exchange = (exchange or (code.split(".", 1)[1] if "." in code else "")).strip().upper()
    resolved_board = board.strip() or _infer_a_share_board(raw_code, resolved_exchange)
    with unit_of_work(connection=connection, immediate=True) as work:
        # 事务内二次确认，避免并发下重复插入。
        if work.connection.execute(
            "SELECT 1 FROM stock_basic_profiles WHERE stock_code = ?", (code,)
        ).fetchone() is not None:
            return False
        work.connection.execute(
            """
            INSERT INTO stock_basic_profiles(
                market_group, exchange, board, stock_code, stock_name,
                listing_date, industry, sw_level1_name, sw_level2_name, sw_level3_name,
                source, is_manual_override
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                market_group or "A", resolved_exchange, resolved_board, code,
                stock_name.strip(), listing_date or None, industry.strip(),
                sw_level1_name.strip(), sw_level2_name.strip(), sw_level3_name.strip(),
                source or "auto_ensure",
            ),
        )
    return True


def upsert_record(
    record: StockBasicProfileInput,
    *,
    source: str = "manual",
    source_version: str = "",
    is_manual_override: bool = True,
    expected_revision: str | None = None,
    create_only: bool = False,
) -> dict[str, Any]:
    # 手工输入：显式空值表示清空；未提交的字段保持原值。批量导入仍走 batch_upsert 合并。
    values = record.model_dump(exclude={"expected_revision", *_SW_FIELDS})
    for field in ("listing_date", "setup_date"):
        values[field] = values[field] or None
    values.update({
        "source": source, "source_version": source_version or record.source_version,
        "is_manual_override": int(is_manual_override),
    })
    columns = list(values)
    update_columns = [
        field for field in columns
        if field != "stock_code" and (field in record.model_fields_set or field in {
            "source", "source_version", "is_manual_override",
        })
    ]
    assignments = [f"{field}=excluded.{field}" for field in update_columns]
    assignments.append("updated_at=datetime('now','localtime')")
    connection = _connection()
    with unit_of_work(connection=connection, immediate=True) as work:
        current = work.connection.execute("SELECT * FROM stock_basic_profiles WHERE stock_code=?", (record.stock_code,)).fetchone()
        if create_only and current is not None:
            raise MasterDataConflictError("股票资料已存在，请打开现有记录编辑")
        if expected_revision is not None:
            check_revision(current, expected_revision)
        work.connection.execute(
            f"""INSERT INTO stock_basic_profiles ({', '.join(columns)})
                VALUES ({', '.join('?' for _ in columns)})
                ON CONFLICT(stock_code) DO UPDATE SET {', '.join(assignments)}""",
            tuple(values.values()),
        )
        return get_record(record.stock_code) or {}


def delete_record(record_id: int) -> bool:
    connection = _connection()
    with unit_of_work(connection=connection, immediate=True) as work:
        cursor = work.connection.execute(
            "DELETE FROM stock_basic_profiles WHERE id = ?", (record_id,)
        )
    return cursor.rowcount > 0


def update_business_info(
    stock_code: str,
    *,
    main_business: str = "",
    business_scope: str = "",
    products: str = "",
    company_intro: str = "",
    setup_date: str | None = None,
    legal_repr: str = "",
    registered_capital: str = "",
    website: str = "",
    province: str = "",
    city: str = "",
    listing_date: str | None = None,
    source: str = "enrich",
    force: bool = False,
    updated_fields: list[str] | None = None,
) -> dict[str, Any] | None:
    incoming = {
        "main_business": main_business, "business_scope": business_scope,
        "products": products, "company_intro": company_intro, "setup_date": setup_date,
        "legal_repr": legal_repr, "registered_capital": registered_capital,
        "website": website, "province": province, "city": city, "listing_date": listing_date,
    }
    connection = _connection()
    # 上游请求完成后才进入事务；在写锁内重新读取，保护请求期间的手工编辑。
    with unit_of_work(connection=connection, immediate=True) as work:
        existing = get_record(stock_code)
        if not existing:
            return None
        changes = {
            key: str(value).strip()
            for key, value in incoming.items()
            if value is not None and str(value).strip()
            and (force or not str(existing.get(key) or "").strip())
            and str(value).strip() != str(existing.get(key) or "")
        }
        if not changes:
            return existing
        assignments = [f"{key} = ?" for key in changes]
        # 记录混合来源但保留手工锁定，后续普通同步仍不能覆盖。
        sources = list(dict.fromkeys(
            (["manual"] if existing["is_manual_override"] else []) + source.split("+")
        ))
        assignments.extend(["source = ?", "updated_at = datetime('now','localtime')"])
        work.connection.execute(
            f"UPDATE stock_basic_profiles SET {', '.join(assignments)} WHERE id = ?",
            (*changes.values(), "+".join(sources), existing["id"]),
        )
        if updated_fields is not None:
            updated_fields.extend(changes)
        return get_record_by_id(existing["id"])


_PROFILE_MERGE_TEXT_FIELDS: tuple[str, ...] = (
    "main_business",
    "business_scope",
    "products",
    "industry",
    "sw_level1_name",
    "sw_level2_name",
    "sw_level3_name",
    "city",
    "province",
    "legal_repr",
    "registered_capital",
    "website",
    "company_intro",
)


def batch_upsert(
    records: Iterable[dict[str, Any]],
    *,
    source: str = "exchange",
    source_version: str = "",
    update_existing_manual: bool = False,
) -> dict[str, int]:
    """批量写入个股资料；合并后内容与现值一致的行跳过更新（不刷新 updated_at）。

    此前每次调用都全量重写存量行（sync-master 一次 ~5000 行 UPDATE），既让
    updated_at 失真也会膨胀 WAL。
    """
    connection = _connection()
    stats = {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0}

    with unit_of_work(connection=connection, immediate=True) as work:
        for item in records:
            code = str(item.get("stock_code") or "").strip().upper()
            if not code:
                stats["skipped"] += 1
                continue

            existing = work.connection.execute(
                "SELECT * FROM stock_basic_profiles WHERE stock_code = ?",
                (code,),
            ).fetchone()

            if existing is not None and existing["is_manual_override"] and not update_existing_manual:
                stats["skipped"] += 1
                continue

            market_group = str(item.get("market_group") or "A").strip()
            exchange = str(item.get("exchange") or "").strip().upper()
            board = str(item.get("board") or "").strip()
            name = str(item.get("stock_name") or "").strip()
            listing_date = item.get("listing_date") or None
            main_business = str(item.get("main_business") or "").strip()
            business_scope = str(item.get("business_scope") or "").strip()
            products = str(item.get("products") or "").strip()
            industry = str(item.get("industry") or "").strip()
            sw_level1_name = ""
            sw_level2_name = ""
            sw_level3_name = ""
            city = str(item.get("city") or "").strip()
            province = str(item.get("province") or "").strip()
            legal_repr = str(item.get("legal_repr") or "").strip()
            registered_capital = str(item.get("registered_capital") or "").strip()
            setup_date = item.get("setup_date") or None
            website = str(item.get("website") or "").strip()
            company_intro = str(item.get("company_intro") or "").strip()

            if existing is None:
                work.connection.execute(
                    """
                    INSERT INTO stock_basic_profiles(
                        market_group, exchange, board, stock_code, stock_name,
                        listing_date, main_business, business_scope, products,
                        industry, sw_level1_name, sw_level2_name, sw_level3_name,
                        city, province, legal_repr, registered_capital, setup_date,
                        website, company_intro, source, source_version, is_manual_override,
                        created_at, updated_at
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, 0,
                        datetime('now','localtime'), datetime('now','localtime')
                    )
                    """,
                    (
                        market_group, exchange, board, code, name,
                        listing_date, main_business, business_scope, products,
                        industry, sw_level1_name, sw_level2_name, sw_level3_name,
                        city, province, legal_repr, registered_capital, setup_date,
                        website, company_intro, source, source_version,
                    ),
                )
                stats["added"] += 1
            else:
                # 复现 UPDATE 的 COALESCE/CASE 合并语义，与现值逐字段比较
                merged = {
                    "market_group": market_group or existing["market_group"],
                    "exchange": exchange or existing["exchange"],
                    "board": board or existing["board"],
                    "stock_name": name or existing["stock_name"] or "",
                    "listing_date": listing_date if listing_date is not None else existing["listing_date"],
                    "setup_date": setup_date if setup_date is not None else existing["setup_date"],
                }
                merged.update({
                    key: content_value or (existing[key] or "")
                    for key, content_value in (
                        ("main_business", main_business),
                        ("business_scope", business_scope),
                        ("products", products),
                        ("industry", industry),
                        ("sw_level1_name", sw_level1_name),
                        ("sw_level2_name", sw_level2_name),
                        ("sw_level3_name", sw_level3_name),
                        ("city", city),
                        ("province", province),
                        ("legal_repr", legal_repr),
                        ("registered_capital", registered_capital),
                        ("website", website),
                        ("company_intro", company_intro),
                    )
                })
                unchanged = all(
                    (merged[key] if merged[key] is None else str(merged[key]))
                    == (existing[key] if existing[key] is None else str(existing[key]))
                    for key in merged
                )
                if unchanged:
                    stats["unchanged"] += 1
                    continue
                work.connection.execute(
                    """
                    UPDATE stock_basic_profiles SET
                        market_group=COALESCE(NULLIF(?, ''), market_group),
                        exchange=COALESCE(NULLIF(?, ''), exchange),
                        board=COALESCE(NULLIF(?, ''), board),
                        stock_name=CASE WHEN ? <> '' THEN ? ELSE stock_name END,
                        listing_date=COALESCE(?, listing_date),
                        main_business=CASE WHEN ? <> '' THEN ? ELSE main_business END,
                        business_scope=CASE WHEN ? <> '' THEN ? ELSE business_scope END,
                        products=CASE WHEN ? <> '' THEN ? ELSE products END,
                        industry=CASE WHEN ? <> '' THEN ? ELSE industry END,
                        sw_level1_name=CASE WHEN ? <> '' THEN ? ELSE sw_level1_name END,
                        sw_level2_name=CASE WHEN ? <> '' THEN ? ELSE sw_level2_name END,
                        sw_level3_name=CASE WHEN ? <> '' THEN ? ELSE sw_level3_name END,
                        city=CASE WHEN ? <> '' THEN ? ELSE city END,
                        province=CASE WHEN ? <> '' THEN ? ELSE province END,
                        legal_repr=CASE WHEN ? <> '' THEN ? ELSE legal_repr END,
                        registered_capital=CASE WHEN ? <> '' THEN ? ELSE registered_capital END,
                        setup_date=COALESCE(?, setup_date),
                        website=CASE WHEN ? <> '' THEN ? ELSE website END,
                        company_intro=CASE WHEN ? <> '' THEN ? ELSE company_intro END,
                        source=?,
                        source_version=?,
                        updated_at=datetime('now','localtime')
                    WHERE id = ?
                    """,
                    (
                        market_group, exchange, board,
                        name, name,
                        listing_date,
                        main_business, main_business,
                        business_scope, business_scope,
                        products, products,
                        industry, industry,
                        sw_level1_name, sw_level1_name,
                        sw_level2_name, sw_level2_name,
                        sw_level3_name, sw_level3_name,
                        city, city,
                        province, province,
                        legal_repr, legal_repr,
                        registered_capital, registered_capital,
                        setup_date,
                        website, website,
                        company_intro, company_intro,
                        source, source_version,
                        existing["id"],
                    ),
                )
                stats["updated"] += 1

    return stats


def get_summary() -> dict[str, Any]:
    connection = _connection()
    total = int(connection.execute("SELECT COUNT(*) FROM stock_basic_profiles").fetchone()[0])
    has_business = int(
        connection.execute("SELECT COUNT(*) FROM stock_basic_profiles WHERE main_business <> ''").fetchone()[0]
    )
    has_listing_date = int(
        connection.execute(
            "SELECT COUNT(*) FROM stock_basic_profiles WHERE listing_date IS NOT NULL AND listing_date <> ''"
        ).fetchone()[0]
    )

    market_counts = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT market_group, COUNT(*) FROM stock_basic_profiles GROUP BY market_group"
        ).fetchall()
    }

    board_counts = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT board, COUNT(*) FROM stock_basic_profiles WHERE board <> '' GROUP BY board ORDER BY COUNT(*) DESC"
        ).fetchall()
    }

    last_updated = connection.execute(
        "SELECT MAX(updated_at) FROM stock_basic_profiles"
    ).fetchone()[0]

    return {
        "total": total,
        "has_business_count": has_business,
        "has_listing_date_count": has_listing_date,
        "market_group_counts": market_counts,
        "board_counts": board_counts,
        "last_updated_at": last_updated,
    }
