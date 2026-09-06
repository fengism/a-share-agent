from __future__ import annotations

import csv
import io
import json
import logging
import urllib.parse
from typing import Any

import requests

from app.configuration.paths import DATA_DIR
from app.infrastructure.providers.ths.business_intro import fetch_stock_business_intro
from app.infrastructure.providers.ths.transport import ThsTransport
from app.modules.stock_profile import importer
from app.modules.stock_profile.models import (
    StockBasicProfileInput,
    StockBasicProfileListResponse,
    StockBasicProfileRecord,
    StockBasicProfileSummary,
    StockProfileEnrichResponse,
    StockProfileImportFileRequest,
    StockProfileImportResponse,
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

_EXCHANGE_MASTER_FILE = DATA_DIR / "official_exchange_stock_master.json"
_BUSINESS_INTRO_DIR = DATA_DIR / "stock_business_intro"
_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://emweb.securities.eastmoney.com/",
}


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
) -> StockBasicProfileRecord:
    row = upsert_record(
        input_data,
        source=source,
        is_manual_override=is_manual_override,
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
    transport = ThsTransport()
    try:
        df = fetch_stock_business_intro(transport, raw_code)
        if df is not None and not df.empty:
            return {k: str(v) for k, v in df.iloc[0].to_dict().items() if v}
    except Exception as e:
        logger.warning("THS business intro fetch error code=%s: %s", raw_code, e)
    return {}


def fetch_eastmoney_company_survey(stock_code: str, exchange: str) -> dict[str, Any]:
    """Fetch company survey from Eastmoney CompanySurveyAjax."""
    raw_code = stock_code.split(".")[0]
    ex = exchange.upper() if exchange else ("SH" if raw_code.startswith("6") else "SZ")
    sec_code = f"{ex}{raw_code}"
    url = f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax?code={sec_code}"

    try:
        resp = requests.get(url, headers=_HTTP_HEADERS, timeout=8)
        if resp.status_code == 200:
            payload = resp.json()
            if isinstance(payload, dict):
                return payload
    except Exception as e:
        logger.warning("Eastmoney survey fetch error code=%s: %s", sec_code, e)
    return {}


def enrich_stock_profile(stock_code: str, *, force: bool = False) -> StockProfileEnrichResponse:
    """补充个股资料：库中已有主营信息时直接返回，缺失才从 THS/东财抓取并更新库。

    force=True 忽略库内已有数据，强制重新联网抓取。此前无论库内是否
    有数据都会抓取并覆盖，force 参数形同虚设。
    """
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
    )

    if result:
        for field in (
            "main_business", "business_scope", "products", "company_intro",
            "setup_date", "legal_repr", "registered_capital", "website",
            "province", "city", "listing_date",
        ):
            if result.get(field):
                updated_fields.append(field)

    return StockProfileEnrichResponse(
        success=True,
        stock_code=existing["stock_code"],
        stock_name=existing["stock_name"],
        updated_fields=updated_fields,
        message=f"已成功补充 {len(updated_fields)} 项基础资料",
    )


def sync_exchange_master_data() -> dict[str, int]:
    """Sync full-market stocks from official_exchange_stock_master.json and sw_industry_classifications."""
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
            except Exception:
                pass

    # 3. Load official exchange master
    if _EXCHANGE_MASTER_FILE.exists():
        try:
            exchange_data = json.loads(_EXCHANGE_MASTER_FILE.read_text(encoding="utf-8"))
            exchanges_dict = exchange_data.get("exchanges") or {}
            for ex_key, ex_slice in exchanges_dict.items():
                for item in ex_slice.get("records") or []:
                    raw_code = str(item.get("code") or "").strip()
                    if not raw_code or not raw_code.isdigit():
                        continue
                    exchange = str(item.get("exchange") or ex_key).strip().upper()
                    full_code = f"{raw_code}.{exchange}"
                    name = str(item.get("name") or "").strip()
                    board = str(item.get("board") or "").strip()
                    industry = str(item.get("industry") or "").strip()
                    listing_date = str(item.get("listing_date") or "").strip() or None

                    # Merge Shenwan industry info
                    sw_info = sw_map.get(full_code) or sw_map.get(raw_code) or {}
                    sw1 = sw_info.get("sw_level1_name", "")
                    sw2 = sw_info.get("sw_level2_name", "")
                    sw3 = sw_info.get("sw_level3_name", "")

                    # Merge business intro if cached
                    intro_items = local_intro_map.get(raw_code) or {}
                    main_business = intro_items.get("主营业务", "")
                    business_scope = intro_items.get("经营范围", "")
                    products = intro_items.get("产品名称") or intro_items.get("产品类型") or ""

                    records_to_upsert.append({
                        "stock_code": full_code,
                        "stock_name": name,
                        "market_group": "A",
                        "exchange": exchange,
                        "board": board,
                        "listing_date": listing_date,
                        "main_business": main_business,
                        "business_scope": business_scope,
                        "products": products,
                        "industry": industry or sw1,
                        "sw_level1_name": sw1,
                        "sw_level2_name": sw2,
                        "sw_level3_name": sw3,
                    })
        except Exception as e:
            logger.error("Failed to parse official_exchange_stock_master.json: %s", e)

    # 4. Also add HK stocks from sw_industry_classifications
    for code, sw_info in sw_map.items():
        if sw_info.get("market_group") == "HK" and "." in code:
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
