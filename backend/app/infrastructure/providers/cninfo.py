"""Cninfo full-market stock-index provider."""

import json
import math
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.market import classify_exchange, normalize_code, normalize_stock_name
from app.infrastructure.http.client import provider_get, provider_post

CNINFO_STOCK_INDEX_URL = "https://www.cninfo.com.cn/new/data/szse_stock.json"
CNINFO_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.cninfo.com.cn/",
    "User-Agent": "Mozilla/5.0 AShareAgent/1.0",
}
_REQUEST_TIMEOUT_SECONDS = 5

CNINFO_ANNOUNCEMENT_QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_ANNOUNCEMENT_DETAIL_URL = "https://www.cninfo.com.cn/new/disclosure/detail"
CNINFO_STATIC_BASE = "https://static.cninfo.com.cn/"
CNINFO_ANNOUNCEMENT_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice",
    "Origin": "https://www.cninfo.com.cn",
    "User-Agent": "Mozilla/5.0 AShareAgent/1.0",
}
CNINFO_ANNOUNCEMENT_MAX_PAGE_SIZE = 30
_CNINFO_ANNOUNCEMENT_TIMEOUT_SECONDS = 10

# 交易所 -> 巨潮 column / orgId 前缀
_CNINFO_EXCHANGE_COLUMN = {"SH": "sse", "SZ": "szse", "BJ": "bjse"}
_CNINFO_ORG_PREFIX = {"SH": "gssh", "SZ": "gssz", "BJ": "gsbj"}
# 巨潮 announcementTime 为北京时间毫秒时间戳
_CHINA_TZ = timezone(timedelta(hours=8))


def _normalize_stock_rows(rows: list[Any]) -> list[dict[str, str]]:
    records_by_code: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or str(row.get("category") or "").strip() != "A股":
            continue
        code = str(row.get("code") or "").strip()
        name = normalize_stock_name(str(row.get("zwjc") or ""))
        if len(code) != 6 or not code.isdigit() or not name:
            continue
        try:
            classify_exchange(code)
        except ValueError:
            continue
        records_by_code.setdefault(code, {"code": code, "name": name})
    return [records_by_code[code] for code in sorted(records_by_code)]


def _announcement_date(value: object) -> str:
    """巨潮 announcementTime 为北京时间毫秒时间戳，转为 yyyy-MM-dd。"""
    try:
        millis = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if millis <= 0:
        return ""
    try:
        return datetime.fromtimestamp(millis / 1000, tz=_CHINA_TZ).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return ""


def _announcement_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _normalize_bulletin(raw: Mapping[str, Any], *, code: str, org_id: str) -> dict[str, str]:
    """将巨潮单条公告转为公告服务统一字段（source 由服务层盖章）。"""
    announcement_id = str(raw.get("announcementId") or "").strip()
    published = _announcement_date(raw.get("announcementTime"))
    adjunct_url = str(raw.get("adjunctUrl") or "").strip().lstrip("/")
    detail_url = ""
    if announcement_id:
        detail_url = (
            f"{CNINFO_ANNOUNCEMENT_DETAIL_URL}?stockCode={code}"
            f"&announcementId={announcement_id}&orgId={org_id}&announcementTime={published}"
        )
    return {
        "id": announcement_id,
        "title": str(raw.get("announcementTitle") or "").strip(),
        "date": published,
        "type": str(raw.get("adjunctType") or "").strip(),
        "type2": "",
        "url": detail_url,
        "pdf_url": f"{CNINFO_STATIC_BASE}{adjunct_url}" if adjunct_url else "",
        "origin": "巨潮资讯网",
    }


class CninfoDataProvider:
    """Fetch Cninfo's full-market A-share code and name index."""

    name = "cninfo"

    def fetch_stock_names(self) -> list[dict[str, str]]:
        response = provider_get(
            CNINFO_STOCK_INDEX_URL,
            headers=CNINFO_HEADERS,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        try:
            payload = response.json()
        except ValueError as error:
            raise RuntimeError("巨潮股票索引返回了无效 JSON") from error
        rows = payload.get("stockList") if isinstance(payload, Mapping) else None
        if not isinstance(rows, list):
            raise RuntimeError("巨潮股票索引返回格式无效")
        return _normalize_stock_rows(rows)

    def fetch_stock_bulletins(self, code: str, page: int = 1, page_size: int = 10) -> dict:
        """抓取巨潮资讯个股公告列表（法定信息披露平台）。

        Param:
            code: 6 位 A 股代码
            page: 页码，从 1 开始
            page_size: 每页条数（1-30）
        Return:
            归一化字典：code、name、page、page_size、total_pages、items
        """
        normalized = normalize_code(code)
        raw_code = normalized.raw
        column = _CNINFO_EXCHANGE_COLUMN.get(normalized.exchange, "szse")
        org_id = f"{_CNINFO_ORG_PREFIX.get(normalized.exchange, 'gssz')}{raw_code}"
        page = max(1, page)
        page_size = min(max(1, page_size), CNINFO_ANNOUNCEMENT_MAX_PAGE_SIZE)
        payload = {
            "pageNum": page,
            "pageSize": page_size,
            "column": column,
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{raw_code},orgId,{org_id}",
            "searchkey": "",
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": "",
        }
        response = provider_post(
            CNINFO_ANNOUNCEMENT_QUERY_URL,
            data=payload,
            headers=CNINFO_ANNOUNCEMENT_HEADERS,
            timeout=_CNINFO_ANNOUNCEMENT_TIMEOUT_SECONDS,
        )
        text = response.text.strip().lstrip("\ufeff")
        if not text:
            raise RuntimeError("巨潮公告接口返回空响应")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as error:
            raise RuntimeError("巨潮公告接口返回了无效 JSON") from error
        if parsed is None:
            parsed = {}
        if not isinstance(parsed, Mapping):
            raise RuntimeError("巨潮公告接口返回格式无效")
        rows = parsed.get("announcements")
        rows = rows if isinstance(rows, list) else []
        items = [
            _normalize_bulletin(row, code=raw_code, org_id=org_id)
            for row in rows
            if isinstance(row, Mapping)
        ]
        name = ""
        for row in rows:
            if isinstance(row, Mapping) and str(row.get("secName") or "").strip():
                name = str(row.get("secName")).strip()
                break
        total = _announcement_int(parsed.get("totalRecordNum"))
        return {
            "code": raw_code,
            "name": name,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
            "items": items,
        }


cninfo_provider = CninfoDataProvider()
