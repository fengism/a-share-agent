"""百度个股与板块资金流能力。"""

import re
from collections.abc import Mapping
from typing import Any

from app.infrastructure.providers.baidu.transport import BaiduTransport, check_result_code

_HISTORY_PAGE_SIZE = 20
_HISTORY_MAX_RECORDS = 120
_AMOUNT_PATTERN = re.compile(r"^([+-]?\d+(?:\.\d+)?)(亿|万|元)?$")


class BaiduFundFlowUnavailableError(ConnectionError):
    """Temporary empty response from Baidu history fund flow."""


def _parse_fund_amount(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").replace(",", "").strip()
    if text in {"", "-", "--", "N/A"}:
        return None
    match = _AMOUNT_PATTERN.fullmatch(text)
    if match is None:
        return None
    number = float(match.group(1))
    multiplier = {"亿": 100_000_000, "万": 10_000, "元": 1, None: 1}[match.group(2)]
    return number * multiplier


def _normalize_history_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    date = str(row.get("showtime") or "").strip()
    if not date:
        raw_time = str(row.get("time") or "").strip()
        if len(raw_time) == 8 and raw_time.isdigit():
            date = f"{raw_time[:4]}-{raw_time[4:6]}-{raw_time[6:]}"
    if len(date) != 10:
        return None
    return {
        "date": date,
        "main_net": _parse_fund_amount(row.get("extMainIn")),
        "small_net": _parse_fund_amount(row.get("littleNetIn")),
        "mid_net": _parse_fund_amount(row.get("mediumNetIn")),
        "large_net": _parse_fund_amount(row.get("largeNetIn")),
        "super_net": _parse_fund_amount(row.get("superNetIn")),
    }


def fetch_stock_fund_flow(transport: BaiduTransport, code: str) -> dict:
    """Fetch Baidu's current-day aggregate fund-flow view."""
    data = transport.get_json(
        "/vapi/v1/fundflow",
        params={
            "finance_type": "stock",
            "fund_flow_type": "",
            "market": "ab",
            "code": code,
            "type": "stock",
            "finClientType": "pc",
        },
    )
    check_result_code(data)
    result = data.get("Result", {}).get("content", {}).get("fundFlowSpread", {}).get("result", {})
    return result if isinstance(result, dict) else {}


def fetch_stock_fund_flow_history(
    transport: BaiduTransport,
    code: str,
    limit: int = _HISTORY_MAX_RECORDS,
) -> list[dict[str, Any]]:
    """Fetch up to 120 daily records using the exclusive date cutoff."""
    target = min(max(1, int(limit)), _HISTORY_MAX_RECORDS)
    records: list[dict[str, Any]] = []
    seen_dates: set[str] = set()
    seen_cutoffs: set[str] = set()
    cutoff: str | None = None
    previous_date: str | None = None

    while len(records) < target:
        params = {
            "code": code,
            "market": "ab",
            "finance_type": "stock",
            "tab": "day",
            "from": "history",
            "rn": str(_HISTORY_PAGE_SIZE),
            "finClientType": "pc",
        }
        if cutoff is not None:
            params["date"] = cutoff
        data = transport.get_json("/vapi/v1/fundsortlist", params=params)
        check_result_code(data)
        result = data.get("Result")
        rows = result.get("content") if isinstance(result, Mapping) else None
        if not isinstance(rows, list):
            raise RuntimeError("百度历史资金流返回格式无效")
        if not rows:
            if not records:
                raise BaiduFundFlowUnavailableError("百度历史资金流返回空数据")
            break

        page_added = 0
        for item in rows:
            if not isinstance(item, Mapping):
                continue
            normalized = _normalize_history_row(item)
            if normalized is None:
                continue
            item_date = str(normalized["date"])
            if item_date in seen_dates:
                continue
            if previous_date is not None and item_date >= previous_date:
                raise RuntimeError("百度历史资金流日期未严格递减")
            seen_dates.add(item_date)
            previous_date = item_date
            records.append(normalized)
            page_added += 1
            if len(records) >= target:
                break
        if page_added == 0:
            raise RuntimeError("百度历史资金流日期未严格递减")
        if len(records) >= target or len(rows) < _HISTORY_PAGE_SIZE:
            break

        last_row = rows[-1]
        next_cutoff = str(last_row.get("time") or "").replace("-", "").strip() if isinstance(last_row, Mapping) else ""
        if len(next_cutoff) != 8 or not next_cutoff.isdigit() or next_cutoff in seen_cutoffs:
            raise RuntimeError("百度历史资金流截止日期无效")
        seen_cutoffs.add(next_cutoff)
        cutoff = next_cutoff

    return records


def fetch_block_fund_flow(transport: BaiduTransport, block_type: str) -> list[dict]:
    data = transport.get_json(
        "/sapi/v1/ranks",
        params={
            "bizType": "fundflow_rank",
            "style": "tablelist",
            "fundflowRankTarget": "block",
            "market": "ab",
            "sortKey": "",
            "sortType": "",
            "blockType": block_type,
            "pn": "0",
            "rn": "200",
            "finClientType": "pc",
        },
        headers=transport.cookie_headers(),
    )
    check_result_code(data)
    return [
        {
            "code": item.get("code", ""),
            "name": item.get("name", ""),
            "mainNetIn": item.get("mainNetIn", 0),
            "mainTotalIn": item.get("mainTotalIn", 0),
            "totalAmount": item.get("totalAmount", 0),
        }
        for item in data.get("Result", {}).get("list", {}).get("body", [])
    ]
