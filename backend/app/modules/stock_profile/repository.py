from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from typing import Any

from app.infrastructure.persistence.connection import get_connection, unit_of_work
from app.modules.stock_profile.models import StockBasicProfileInput


def _connection() -> sqlite3.Connection:
    return get_connection("industry")


def _record(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["is_manual_override"] = bool(result["is_manual_override"])
    return result


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

    return [_record(row) for row in rows], total


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
    return _record(row) if row else None


def get_record_by_id(record_id: int) -> dict[str, Any] | None:
    row = _connection().execute(
        "SELECT * FROM stock_basic_profiles WHERE id = ?", (record_id,)
    ).fetchone()
    return _record(row) if row else None


def upsert_record(
    record: StockBasicProfileInput,
    *,
    source: str = "manual",
    source_version: str = "",
    is_manual_override: bool = True,
) -> dict[str, Any]:
    connection = _connection()
    with unit_of_work(connection=connection, immediate=True) as work:
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
                ?, ?, ?, ?, ?,
                datetime('now','localtime'), datetime('now','localtime')
            )
            ON CONFLICT(stock_code) DO UPDATE SET
                market_group=excluded.market_group,
                exchange=excluded.exchange,
                board=excluded.board,
                stock_name=excluded.stock_name,
                listing_date=COALESCE(NULLIF(excluded.listing_date, ''), stock_basic_profiles.listing_date),
                main_business=CASE WHEN excluded.main_business <> '' THEN excluded.main_business ELSE stock_basic_profiles.main_business END,
                business_scope=CASE WHEN excluded.business_scope <> '' THEN excluded.business_scope ELSE stock_basic_profiles.business_scope END,
                products=CASE WHEN excluded.products <> '' THEN excluded.products ELSE stock_basic_profiles.products END,
                industry=CASE WHEN excluded.industry <> '' THEN excluded.industry ELSE stock_basic_profiles.industry END,
                sw_level1_name=CASE WHEN excluded.sw_level1_name <> '' THEN excluded.sw_level1_name ELSE stock_basic_profiles.sw_level1_name END,
                sw_level2_name=CASE WHEN excluded.sw_level2_name <> '' THEN excluded.sw_level2_name ELSE stock_basic_profiles.sw_level2_name END,
                sw_level3_name=CASE WHEN excluded.sw_level3_name <> '' THEN excluded.sw_level3_name ELSE stock_basic_profiles.sw_level3_name END,
                city=CASE WHEN excluded.city <> '' THEN excluded.city ELSE stock_basic_profiles.city END,
                province=CASE WHEN excluded.province <> '' THEN excluded.province ELSE stock_basic_profiles.province END,
                legal_repr=CASE WHEN excluded.legal_repr <> '' THEN excluded.legal_repr ELSE stock_basic_profiles.legal_repr END,
                registered_capital=CASE WHEN excluded.registered_capital <> '' THEN excluded.registered_capital ELSE stock_basic_profiles.registered_capital END,
                setup_date=COALESCE(NULLIF(excluded.setup_date, ''), stock_basic_profiles.setup_date),
                website=CASE WHEN excluded.website <> '' THEN excluded.website ELSE stock_basic_profiles.website END,
                company_intro=CASE WHEN excluded.company_intro <> '' THEN excluded.company_intro ELSE stock_basic_profiles.company_intro END,
                source=excluded.source,
                source_version=excluded.source_version,
                is_manual_override=excluded.is_manual_override,
                updated_at=datetime('now','localtime')
            """,
            (
                record.market_group,
                record.exchange,
                record.board,
                record.stock_code,
                record.stock_name,
                record.listing_date,
                record.main_business,
                record.business_scope,
                record.products,
                record.industry,
                record.sw_level1_name,
                record.sw_level2_name,
                record.sw_level3_name,
                record.city,
                record.province,
                record.legal_repr,
                record.registered_capital,
                record.setup_date,
                record.website,
                record.company_intro,
                source,
                source_version,
                1 if is_manual_override else 0,
            ),
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
) -> dict[str, Any] | None:
    code = stock_code.strip().upper()
    existing = get_record(code)
    if not existing:
        return None

    updates: list[str] = []
    params: list[object] = []

    if main_business:
        updates.append("main_business = ?")
        params.append(main_business)
    if business_scope:
        updates.append("business_scope = ?")
        params.append(business_scope)
    if products:
        updates.append("products = ?")
        params.append(products)
    if company_intro:
        updates.append("company_intro = ?")
        params.append(company_intro)
    if setup_date:
        updates.append("setup_date = ?")
        params.append(setup_date)
    if legal_repr:
        updates.append("legal_repr = ?")
        params.append(legal_repr)
    if registered_capital:
        updates.append("registered_capital = ?")
        params.append(registered_capital)
    if website:
        updates.append("website = ?")
        params.append(website)
    if province:
        updates.append("province = ?")
        params.append(province)
    if city:
        updates.append("city = ?")
        params.append(city)
    if listing_date and not existing.get("listing_date"):
        updates.append("listing_date = ?")
        params.append(listing_date)

    if not updates:
        return existing

    updates.append("updated_at = datetime('now','localtime')")
    params.append(existing["id"])

    connection = _connection()
    with unit_of_work(connection=connection, immediate=True) as work:
        work.connection.execute(
            f"UPDATE stock_basic_profiles SET {', '.join(updates)} WHERE id = ?",
            params,
        )

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
            sw_level1_name = str(item.get("sw_level1_name") or "").strip()
            sw_level2_name = str(item.get("sw_level2_name") or "").strip()
            sw_level3_name = str(item.get("sw_level3_name") or "").strip()
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
