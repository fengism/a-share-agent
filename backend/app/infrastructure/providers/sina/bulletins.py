"""Sina Finance 个股公告列表（CB_AllService.getBulletinList）。"""

import logging
from typing import Any

import requests

from app.constants.http import SINA_FINANCE_HEADERS
from app.constants.market import SINA_BULLETIN_LIST_URL
from app.infrastructure.providers.sina.parsing import parse_jsonp

logger = logging.getLogger(__name__)

BULLETIN_REQUEST_TIMEOUT_SECONDS = 15


def _parse_payload(response: requests.Response) -> dict:
    """解析公告接口返回，兼容 JSON 与 JSONP 两种封装。"""
    payload = response.text.strip()
    if payload.startswith("{"):
        return response.json()
    return parse_jsonp(payload)


def _normalize_date(value: Any) -> str:
    text = str(value or "").strip()
    return text.split(" ")[0] if " " in text else text


def _normalize_item(entry: dict) -> dict:
    return {
        "id": str(entry.get("ID") or "").strip(),
        "title": str(entry.get("title") or entry.get("stitle") or "").strip(),
        "date": _normalize_date(entry.get("date")),
        "type": str(entry.get("type") or "").strip(),
        "type2": str(entry.get("type2") or "").strip(),
        "url": str(entry.get("url") or "").strip(),
        "pdf_url": str(entry.get("pdf_path") or "").strip(),
        "origin": str(entry.get("origin") or "").strip(),
    }


def fetch_stock_bulletins(
    session: requests.Session,
    code: str,
    page: int = 1,
    page_size: int = 10,
    notice_type: str = "",
) -> dict:
    """抓取新浪个股公告列表。

    Param:
        session: 新浪独立请求会话
        code: 6 位股票代码
        page: 页码，从 1 开始
        page_size: 每页条数
        notice_type: 公告类型筛选，留空返回全部
    Return:
        归一化字典：code、name、page、page_size、total_pages、items
    """
    response = session.get(
        SINA_BULLETIN_LIST_URL,
        params={
            "PaperCode": code,
            "Page": max(1, page),
            "Display": max(1, page_size),
            "Type": notice_type or "",
        },
        headers=SINA_FINANCE_HEADERS,
        timeout=BULLETIN_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = _parse_payload(response)
    result = payload.get("result") if isinstance(payload, dict) else None
    status = (result or {}).get("status") or {}
    if status.get("code") != 0:
        raise ValueError(f"新浪公告接口返回异常: {status}")
    data = (result or {}).get("data") or {}
    otherinfo = data.get("otherinfo") or {}
    entries = data.get("data") or []
    if not isinstance(entries, list):
        entries = []
    items = [_normalize_item(entry) for entry in entries if isinstance(entry, dict)]
    try:
        total_pages = int(otherinfo.get("page_count") or 0)
    except (TypeError, ValueError):
        total_pages = 0
    return {
        "code": code,
        "name": str(otherinfo.get("PaperName") or "").strip(),
        "page": max(1, page),
        "page_size": max(1, page_size),
        "total_pages": total_pages,
        "items": items,
    }
