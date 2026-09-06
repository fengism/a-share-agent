"""Sina Finance 个股研报评级列表（ReportService.getList）。"""

import logging
import math
from typing import Any

import requests

from app.constants.http import SINA_FINANCE_HEADERS
from app.constants.market import SINA_REPORT_LIST_URL
from app.infrastructure.providers.sina.parsing import parse_jsonp

logger = logging.getLogger(__name__)

REPORT_REQUEST_TIMEOUT_SECONDS = 15


def _parse_payload(response: requests.Response) -> dict:
    """解析研报接口返回，兼容 JSON 与 JSONP 两种封装。"""
    payload = response.text.strip()
    if payload.startswith("{"):
        return response.json()
    return parse_jsonp(payload)


def _normalize_goal_price(value: Any) -> float | None:
    try:
        goal_price = float(value)
    except (TypeError, ValueError):
        return None
    return goal_price if goal_price > 0 else None


def _normalize_item(entry: dict) -> dict:
    return {
        "id": str(entry.get("report_id") or entry.get("id") or "").strip(),
        "title": str(entry.get("title") or "").strip(),
        "org": str(entry.get("orgname") or "").strip(),
        "author": str(entry.get("author") or "").strip(),
        "date": str(entry.get("adddate") or "").strip(),
        "rating": str(entry.get("rating") or "").strip(),
        "goal_price": _normalize_goal_price(entry.get("goal_price")),
        "report_type": str(entry.get("rpt_name") or "").strip(),
        "url": str(entry.get("detail_url") or "").strip(),
    }


def fetch_stock_reports(
    session: requests.Session,
    symbol: str,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    """抓取新浪个股研报评级列表。

    Param:
        session: 新浪独立请求会话
        symbol: 带交易所前缀的股票代码（如 sz002273）
        page: 页码，从 1 开始
        page_size: 每页条数
    Return:
        归一化字典：code、page、page_size、total_count、total_pages、items
    """
    response = session.get(
        SINA_REPORT_LIST_URL,
        params={
            "symbol": symbol,
            "t1": "all",
            "kind": "search",
            "num": max(1, page_size),
            "page": max(1, page),
        },
        headers=SINA_FINANCE_HEADERS,
        timeout=REPORT_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = _parse_payload(response)
    result = payload.get("result") if isinstance(payload, dict) else None
    status = (result or {}).get("status") or {}
    if status.get("code") != 0:
        raise ValueError(f"新浪研报接口返回异常: {status}")
    data = (result or {}).get("data") or {}
    entries = data.get("data") or []
    if not isinstance(entries, list):
        entries = []
    items = [_normalize_item(entry) for entry in entries if isinstance(entry, dict)]
    try:
        total_count = int(data.get("total") or 0)
    except (TypeError, ValueError):
        total_count = 0
    return {
        "code": symbol,
        "page": max(1, page),
        "page_size": max(1, page_size),
        "total_count": total_count,
        "total_pages": math.ceil(total_count / max(1, page_size)),
        "items": items,
    }
