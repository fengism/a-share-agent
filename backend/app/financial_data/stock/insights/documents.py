"""Bounded announcement/report discovery over existing providers; never invent a PDF."""

import asyncio
import logging
import re
from collections.abc import Awaitable
from datetime import date
from typing import Any, Literal

from app.financial_data.stock.insights.bulletins import get_stock_bulletins
from app.financial_data.stock.insights.reports import get_stock_reports

logger = logging.getLogger(__name__)
DocumentKind = Literal["all", "announcement", "periodic_report", "research_report"]
_PERIODIC = re.compile(r"年度报告|半年度报告|季度报告|年报|中报|季报")


def _date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


async def get_stock_documents(
    code: str,
    kind: DocumentKind = "all",
    start_date: str = "",
    end_date: str = "",
    keyword: str = "",
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    if not re.fullmatch(r"\d{6}", code, re.ASCII):
        raise ValueError("仅支持6位A股代码；海外公司请使用网页/PDF检索")
    if kind not in {"all", "announcement", "periodic_report", "research_report"}:
        raise ValueError("不支持的文档类型")
    if not 1 <= page <= 100 or not 1 <= limit <= 30:
        raise ValueError("page需为1-100，limit需为1-30")
    start, end = _date(start_date), _date(end_date)
    if (start_date and (start is None or start.isoformat() != start_date)) or (end_date and (end is None or end.isoformat() != end_date)):
        raise ValueError("日期需为YYYY-MM-DD")
    if start and end and start > end:
        raise ValueError("开始日期不能晚于结束日期")
    labels = []
    tasks: list[Awaitable[Any]] = []
    if kind != "research_report":
        labels.append("announcements")
        tasks.append(get_stock_bulletins(code, page=page, page_size=30))
    if kind in {"all", "research_report"}:
        labels.append("research_reports")
        tasks.append(get_stock_reports(code, months=24))
    outcomes = await asyncio.gather(*tasks, return_exceptions=True)
    items: list[dict[str, Any]] = []
    failed: list[str] = []
    next_page = None
    undated = 0
    seen = set()
    for label, outcome in zip(labels, outcomes, strict=True):
        if isinstance(outcome, asyncio.CancelledError):
            raise outcome
        if isinstance(outcome, BaseException):
            failed.append(label)
            logger.warning("文档目录来源失败: code=%s source=%s error_type=%s", code, label, type(outcome).__name__)
            continue
        if label == "announcements" and outcome.total_pages > page:
            next_page = page + 1
        for entry in outcome.items:
            title = entry.title
            if kind == "periodic_report" and not _PERIODIC.search(title):
                continue
            if keyword.strip() and keyword.strip().casefold() not in title.casefold():
                continue
            published = _date(entry.date)
            if (start or end) and published is None:
                undated += 1
                continue
            if published and ((start and published < start) or (end and published > end)):
                continue
            key = (label, entry.id, entry.url)
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "id": entry.id, "title": title,
                "document_kind": "research_report" if label == "research_reports" else "periodic_report" if _PERIODIC.search(title) else "announcement",
                "published_at": entry.date, "report_period": None,
                "url": entry.url, "pdf_url": getattr(entry, "pdf_url", ""),
                "publisher": getattr(entry, "org", "") or getattr(entry, "origin", ""),
                "source": entry.source, "source_api": entry.source_api,
                "content_status": "not_fetched",
            })
    items.sort(key=lambda item: (_date(item["published_at"]) or date.min, item["title"]), reverse=True)
    return {
        "code": code, "kind": kind,
        "status": "unavailable" if len(failed) == len(labels) else "partial" if failed else "available" if items else "empty",
        "items": items[:limit], "matched_count_in_fetched_window": len(items),
        "returned_count": min(limit, len(items)), "truncated": len(items) > limit,
        "failed_sources": failed, "undated_excluded": undated,
        "next_announcement_page": next_page,
        "coverage": {"complete": False, "announcement_page": page if "announcements" in labels else None,
                     "research_months": 24 if "research_reports" in labels else None,
                     "research_max_pages": 3 if "research_reports" in labels else None},
        "caveats": ["仅目录线索，不是公告或研报正文；使用pdf_url调用read_pdf，或url调用web_fetch。",
                    "公告只扫描指定页，空结果不代表该期间没有披露；研报最多近24个月/3页。",
                    "发布日期不等于报告期；报告期必须阅读原文确认。券商研报不属于公司公告。"],
    }
