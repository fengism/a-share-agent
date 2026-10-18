from __future__ import annotations

import csv
import io
import json
import logging
import urllib.parse
from typing import Any

from app.configuration.paths import DATA_DIR
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore, misc_semaphore
from app.core.exceptions import UpstreamUnavailableError
from app.financial_data.stock.profile.exchange_master import ExchangeStockMaster
from app.financial_data.stock.public import get_exchange_stock_master
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider
from app.modules.stock_profile import importer
from app.modules.stock_profile.models import (
    StockBasicProfileInput,
    StockBasicProfileListResponse,
    StockBasicProfileRecord,
    StockBasicProfileSummary,
    StockProfileEnrichResponse,
    StockProfileImportFileRequest,
    StockProfileImportResponse,
    StockProfileSyncResponse,
)
from app.modules.stock_profile.repository import (
    batch_upsert,
    delete_record,
    get_record,
    get_summary,
    list_records,
    update_business_info,
    upsert_record,
)

logger = logging.getLogger(__name__)

_BUSINESS_INTRO_DIR = DATA_DIR / "stock_business_intro"


def list_profiles(
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
) -> StockBasicProfileListResponse:
    rows, total = list_records(
        query=query,
        market_group=market_group,
        exchange=exchange,
        board=board,
        has_business=has_business,
        has_listing_date=has_listing_date,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    items = [StockBasicProfileRecord.model_validate(row) for row in rows]
    return StockBasicProfileListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


def get_profile(stock_code: str) -> StockBasicProfileRecord | None:
    row = get_record(stock_code)
    if not row:
        return None
    return StockBasicProfileRecord.model_validate(row)


def save_profile(
    input_data: StockBasicProfileInput,
    *,
    source: str = "manual",
    is_manual_override: bool = True,
    expected_revision: str | None = None,
    create_only: bool = False,
) -> StockBasicProfileRecord:
    row = upsert_record(
        input_data,
        source=source,
        is_manual_override=is_manual_override,
        expected_revision=expected_revision,
        create_only=create_only,
    )
    return StockBasicProfileRecord.model_validate(row)


def remove_profile(record_id: int) -> bool:
    return delete_record(record_id)


def get_profile_summary() -> StockBasicProfileSummary:
    raw = get_summary()
    return StockBasicProfileSummary.model_validate(raw)


def fetch_ths_business_intro(code: str) -> dict[str, str]:
    """Fetch business intro from THS."""
    raw_code = code.split(".")[0]
    try:
        df = provider_gateway.call_sync(
            "ths",
            "fetch_stock_business_intro",
            lambda: get_provider("ths").fetch_stock_business_intro(raw_code),
        )
        if df is not None and not df.empty:
            return {k: str(v) for k, v in df.iloc[0].to_dict().items() if v}
    except Exception as e:
        logger.warning("THS business intro fetch error code=%s: %s", raw_code, e)
    return {}


def fetch_eastmoney_company_survey(stock_code: str, exchange: str) -> dict[str, Any]:
    """Fetch company survey from Eastmoney CompanySurveyAjax."""
    try:
        return provider_gateway.call_sync(
            "eastmoney",
            "fetch_company_survey",
            lambda: get_provider("eastmoney").fetch_company_survey(stock_code, exchange),
        )
    except Exception as error:
        logger.warning("Eastmoney survey fetch error code=%s: %s", stock_code, error)
        return {}


def _ensure_skeleton_for_enrich(stock_code: str) -> bool:
    """为显式补充建档；代码无法归一或非 A 股时返回 False。"""
    try:
        from app.modules.code_normalization import normalize_stock_identity
        from app.modules.stock_profile.repository import ensure_basic_skeleton

        full_code, exchange, market = normalize_stock_identity(stock_code)
        return ensure_basic_skeleton(
            stock_code=full_code,
            exchange=exchange,
            market_group=market,
            source="enrich",
        )
    except Exception as error:
        logger.debug("补充建档失败: code=%s error=%s", stock_code, error)
        return False


def enrich_stock_profile(stock_code: str, *, force: bool = False) -> StockProfileEnrichResponse:
    """补充个股资料：库中已有主营信息时直接返回，缺失才从 THS/东财抓取并更新库。

    普通补充仅写入空字段；force=True 明确允许刷新已有值（包含手工资料）。
    """
    existing = get_record(stock_code)
    if not existing:
        # 显式补充是管理员动作：允许为新股票先建最小档案，再填充主营/公司资料。
        if _ensure_skeleton_for_enrich(stock_code):
            existing = get_record(stock_code)
    if not existing:
        return StockProfileEnrichResponse(
            success=False,
            stock_code=stock_code,
            stock_name="",
            updated_fields=[],
            message=f"未找到股票资料记录: {stock_code}",
        )

    if not force and str(existing.get("main_business") or "").strip():
        return StockProfileEnrichResponse(
            success=True,
            stock_code=existing["stock_code"],
            stock_name=existing["stock_name"],
            updated_fields=[],
            message="库中已有主营资料，跳过联网抓取（如需刷新请使用强制模式）",
        )

    code_raw = existing["stock_code"].split(".")[0]
    exchange = existing.get("exchange", "")
    updated_fields: list[str] = []

    # 1. Fetch from THS
    ths_data = fetch_ths_business_intro(code_raw)
    main_business = ths_data.get("主营业务", "")
    business_scope = ths_data.get("经营范围", "")
    products = ths_data.get("产品名称") or ths_data.get("产品类型") or ""

    # 2. Fetch from Eastmoney
    em_data = fetch_eastmoney_company_survey(code_raw, exchange)
    jbzl = em_data.get("jbzl") or {}
    fxxg = em_data.get("fxxg") or {}

    company_intro = jbzl.get("gsjj", "")
    legal_repr = jbzl.get("frdb", "")
    registered_capital = jbzl.get("zczb", "")
    website = jbzl.get("gswz", "")
    province = jbzl.get("qy", "")
    city = jbzl.get("bgdz", "") or jbzl.get("zcdz", "")
    setup_date = fxxg.get("clrq") or None
    listing_date = fxxg.get("ssrq") or None

    if not business_scope and jbzl.get("jyfw"):
        business_scope = jbzl.get("jyfw", "")

    # Perform update
    result = update_business_info(
        stock_code,
        main_business=main_business,
        business_scope=business_scope,
        products=products,
        company_intro=company_intro,
        setup_date=setup_date,
        legal_repr=legal_repr,
        registered_capital=registered_capital,
        website=website,
        province=province,
        city=city,
        listing_date=listing_date,
        source="ths+eastmoney",
        force=force,
        updated_fields=updated_fields,
    )

    # 3. 联动补充个股概念（若该股票尚未维护概念）
    try:
        from app.infrastructure.providers.ths.provider import ths_provider
        from app.modules.stock_concept.repository import get_record as get_concept_record
        from app.modules.stock_concept.repository import upsert_import_records
        c_record = get_concept_record(stock_code)
        if not c_record or not c_record.get("concepts"):
            live_concepts = ths_provider.fetch_stock_concepts(code_raw)
            if live_concepts:
                upsert_import_records(
                    [{
                        "stock_code": stock_code,
                        "stock_name": existing.get("stock_name", ""),
                        "market_group": existing.get("market_group", "A"),
                        "exchange_suffix": existing.get("exchange", "SZ"),
                        "concepts": live_concepts,
                    }],
                    source_version="ths_online_auto",
                    force_override=False,
                )
                updated_fields.append("concepts")
    except Exception as e:
        logger.debug("个股资料补充时联动获取概念跳过 code=%s: %s", stock_code, e)

    if not result:
        return StockProfileEnrichResponse(
            success=False, stock_code=existing["stock_code"], stock_name=existing["stock_name"],
            updated_fields=[], message="补充期间记录已被删除，未写入资料",
        )
    has_upstream_data = any(str(value or "").strip() for value in (
        main_business, business_scope, products, company_intro, setup_date,
        legal_repr, registered_capital, website, province, city, listing_date,
    ))
    if updated_fields:
        message = f"已成功补充 {len(updated_fields)} 项基础资料"
    elif has_upstream_data:
        message = "未新增资料：返回内容无变化或已有字段受保护"
    else:
        message = "上游未返回有效资料，未修改现有数据，请稍后重试"
    return StockProfileEnrichResponse(
        success=has_upstream_data,
        stock_code=existing["stock_code"], stock_name=existing["stock_name"],
        updated_fields=updated_fields, message=message,
    )


async def auto_enrich_pending_profiles(batch_size: int = 50, delay_seconds: float = 0.5) -> dict[str, int]:
    """在后台自动为缺失主营业务的股票平滑补充资料（免 Token，使用同花顺/东财公开源）。"""
    import asyncio
    rows, total = list_records(has_business=False, page=1, page_size=batch_size, sort_by="stock_code")
    if not rows:
        return {"processed": 0, "enriched": 0, "remaining": 0}

    enriched_count = 0
    for record in rows:
        code = record.get("stock_code")
        if not code:
            continue
        try:
            res = await call_blocking(enrich_stock_profile, code, force=False, semaphore=misc_semaphore)
            if res.success and res.updated_fields:
                enriched_count += 1
        except Exception as exc:
            logger.debug("后台自动补充个股资料异常 code=%s: %s", code, exc)
        await asyncio.sleep(delay_seconds)

    remaining = max(0, total - len(rows))
    return {"processed": len(rows), "enriched": enriched_count, "remaining": remaining}


async def sync_exchange_master_data() -> StockProfileSyncResponse:
    """显式同步官方 A 股三大交易所名录与港股全量官方股票名录。"""
    from app.financial_data.hk.search_index import hk_stock_search_index

    master = await get_exchange_stock_master(force=True)
    if not master.records:
        raise UpstreamUnavailableError("交易所名录同步失败：没有可用数据，现有资料未修改")

    # 并发获取港股全量名录
    try:
        hk_records = await hk_stock_search_index.get_all_records()
    except Exception as exc:
        logger.warning("港股名录获取异常，将仅使用申万港股映射: %s", exc)
        hk_records = ()

    stats = await call_blocking(_merge_exchange_master, master, hk_records, semaphore=database_semaphore)
    return StockProfileSyncResponse(
        **stats, complete=master.complete and not master.failed_exchanges,
        failed_exchanges=master.failed_exchanges, stale_exchanges=master.stale_exchanges,
        fetched_at=master.fetched_at,
    )


def _merge_exchange_master(master: ExchangeStockMaster, hk_records: tuple[Any, ...] = ()) -> dict[str, int]:
    from app.infrastructure.persistence.connection import get_connection

    records_to_upsert: list[dict[str, Any]] = []

    # 1. Load Shenwan industries mapping from industry_data.db
    sw_conn = get_connection("industry")
    sw_rows = sw_conn.execute(
        """
        SELECT stock_code, stock_name, market_group, exchange_suffix,
               sw_level1_name, sw_level2_name, sw_level3_name
        FROM sw_industry_classifications
        """
    ).fetchall()

    sw_map: dict[str, dict[str, Any]] = {}
    for row in sw_rows:
        code = str(row["stock_code"]).strip().upper()
        sw_map[code] = dict(row)
        raw_code = code.split(".")[0]
        sw_map.setdefault(raw_code, dict(row))

    # 2. Check local snapshot directory for pre-cached THS business intro files
    local_intro_map: dict[str, dict[str, str]] = {}
    if _BUSINESS_INTRO_DIR.exists():
        for file in _BUSINESS_INTRO_DIR.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                items = data.get("items") or {}
                if items:
                    local_intro_map[file.stem] = items
            except Exception as error:
                logger.debug("主营资料快照读取失败 file=%s: %s", file.name, error)

    # 3. 合并经过官方服务校验且带时效信息的名录，不直接读取未校验的快照。
    for item in master.records:
        full_code = f"{item.code}.{item.exchange}"
        sw_info = sw_map.get(full_code) or {}
        intro_items = local_intro_map.get(item.code) or {}
        records_to_upsert.append({
            "stock_code": full_code, "stock_name": item.name,
            "market_group": "A", "exchange": item.exchange, "board": item.board or "",
            "listing_date": item.listing_date,
            "main_business": intro_items.get("主营业务", ""),
            "business_scope": intro_items.get("经营范围", ""),
            "products": intro_items.get("产品名称") or intro_items.get("产品类型") or "",
            "industry": item.industry or sw_info.get("sw_level1_name", ""),
        })

    # 4. 合并全量港股股票名录（来自港交所/新浪官方索引）
    seen_hk_codes: set[str] = set()
    for hk_item in hk_records:
        raw_digits = str(hk_item.code).strip()
        code_5 = raw_digits.zfill(5)
        full_code = f"{code_5}.HK"
        seen_hk_codes.add(full_code)
        seen_hk_codes.add(code_5)

        sw_info = sw_map.get(full_code) or sw_map.get(code_5) or {}
        intro_items = local_intro_map.get(code_5) or local_intro_map.get(raw_digits) or {}
        records_to_upsert.append({
            "stock_code": full_code,
            "stock_name": hk_item.name,
            "market_group": "HK",
            "exchange": "HK",
            "board": "港股主板",
            "main_business": intro_items.get("主营业务", ""),
            "business_scope": intro_items.get("经营范围", ""),
            "products": intro_items.get("产品名称") or intro_items.get("产品类型") or "",
            "industry": sw_info.get("sw_level1_name", ""),
            "sw_level1_name": sw_info.get("sw_level1_name", ""),
            "sw_level2_name": sw_info.get("sw_level2_name", ""),
            "sw_level3_name": sw_info.get("sw_level3_name", ""),
        })

    # 5. 补充 sw_industry_classifications 中可能存在但不在 hk_records 里的港股通标的
    for code, sw_info in sw_map.items():
        if sw_info.get("market_group") == "HK" and "." in code:
            if code in seen_hk_codes:
                continue
            raw_code = code.split(".")[0]
            intro_items = local_intro_map.get(raw_code) or {}
            records_to_upsert.append({
                "stock_code": code,
                "stock_name": sw_info.get("stock_name", ""),
                "market_group": "HK",
                "exchange": "HK",
                "board": "港股主板",
                "main_business": intro_items.get("主营业务", ""),
                "business_scope": intro_items.get("经营范围", ""),
                "products": intro_items.get("产品名称") or intro_items.get("产品类型") or "",
                "industry": sw_info.get("sw_level1_name", ""),
                "sw_level1_name": sw_info.get("sw_level1_name", ""),
                "sw_level2_name": sw_info.get("sw_level2_name", ""),
                "sw_level3_name": sw_info.get("sw_level3_name", ""),
            })

    if records_to_upsert:
        return batch_upsert(
            records_to_upsert,
            source="exchange_master_sync",
            source_version="v1",
        )
    return {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0}


_PROFILE_EXPORT_COLUMNS: tuple[tuple[str, str], ...] = (
    # (导出表头, 记录字段)；表头与 importer 的列名候选保持一致，导出文件可直接改后再导入
    ("股票代码", "stock_code"),
    ("股票简称", "stock_name"),
    ("交易所", "exchange"),
    ("板块", "board"),
    ("上市日期", "listing_date"),
    ("所属行业", "industry"),
    ("申万一级行业", "sw_level1_name"),
    ("申万二级行业", "sw_level2_name"),
    ("申万三级行业", "sw_level3_name"),
    ("主营业务", "main_business"),
    ("经营范围", "business_scope"),
    ("主要产品", "products"),
    ("省份", "province"),
    ("城市", "city"),
    ("法定代表人", "legal_repr"),
    ("注册资本", "registered_capital"),
    ("成立日期", "setup_date"),
    ("网址", "website"),
    ("公司简介", "company_intro"),
    ("数据来源", "source"),
    ("更新时间", "updated_at"),
)


def import_profiles(request: StockProfileImportFileRequest) -> StockProfileImportResponse:
    """解析上传的 Excel/CSV 并批量写入个股资料库（内容无变化的行自动跳过）。"""
    content = importer.decode_file(request.content_base64)
    parsed = importer.parse_data(content, request.filename)
    stats = batch_upsert(
        parsed.records,
        source="import",
        source_version=importer.default_source_version(request.filename),
        update_existing_manual=request.update_manual,
    )
    return StockProfileImportResponse(
        total_rows=parsed.total_rows,
        added=stats["added"],
        updated=stats["updated"],
        unchanged=stats["unchanged"],
        skipped=stats["skipped"],
        invalid_rows=parsed.invalid_rows,
        warnings=parsed.warnings,
    )


def export_profiles_csv(
    *,
    query: str = "",
    market_group: str = "",
    exchange: str = "",
    board: str = "",
    has_business: bool | None = None,
    has_listing_date: bool | None = None,
) -> tuple[bytes, str]:
    """按筛选条件导出全部个股资料为带 BOM 的 CSV（Excel 可直接打开）。"""
    records, _total = list_records(
        query=query,
        market_group=market_group,
        exchange=exchange,
        board=board,
        has_business=has_business,
        has_listing_date=has_listing_date,
        page=1,
        page_size=0,
    )

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([header for header, _field in _PROFILE_EXPORT_COLUMNS])
    for record in records:
        writer.writerow([
            "" if record.get(field) is None else str(record.get(field, ""))
            for _header, field in _PROFILE_EXPORT_COLUMNS
        ])

    filename = "stock_profile_export.csv"
    encoded_fn = urllib.parse.quote(filename)
    disposition = f"attachment; filename*=UTF-8''{encoded_fn}"
    csv_bytes = output.getvalue().encode("utf-8")
    return csv_bytes, disposition
