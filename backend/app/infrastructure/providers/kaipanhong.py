from datetime import date, datetime

from app.core.market import market_today
from app.core.parsing import parse_float
from app.core.timezones import SHANGHAI_TIMEZONE
from app.infrastructure.http.client import parse_text_json, provider_post

_REALTIME_URL = "https://apphwshhq.kaipanhong.com/w1/api/index.php"
_HISTORY_URL = "https://apphis.kaipanhong.com/w1/api/index.php"
_BASE_PARAMS = {
    "PhoneOSNew": "1",
    "DeviceID": "1a609dd6-b2b8-3bf9-ac40-a77581551454",
    "VerSion": "6.0.6",
    "Token": "0",
    "Red": "1",
    "apiv": "w45",
    "UserID": "0",
}
_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; 2206123SC Build/c069a49.2)",
    "Accept-Encoding": "gzip",
}
_HISTORY_PAGE_SIZE = 50
_HISTORY_MAX_PAGES = 120
_SECTOR_STOCKS_PAGE_SIZE = 1000
_SECTOR_STOCKS_MAX_PAGES = 5
_HISTORY_CATEGORY_PIDS = {
    "limit_up": "4",
    "limit_down": "3",
    "wind_vane": "6",
}


def _safe_int(value: object) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _row_value(row: list, index: int, default=None):
    return row[index] if index < len(row) else default


def _format_limit_up_time(value: object) -> str:
    timestamp = _safe_int(value)
    if timestamp <= 0:
        return ""
    return datetime.fromtimestamp(timestamp, tz=SHANGHAI_TIMEZONE).strftime("%H:%M:%S")


def _normalize_stock_rows(rows: list) -> list[dict]:
    stocks = []
    for row in rows:
        if not isinstance(row, list):
            continue
        code = str(_row_value(row, 0, "") or "").strip()
        name = str(_row_value(row, 1, "") or "").strip()
        if not code or not name:
            continue
        stocks.append(
            {
                "code": code,
                "name": name,
                "board_count": _safe_int(_row_value(row, 2)),
                "limit_up_time": _format_limit_up_time(_row_value(row, 3)),
                "sector_code": str(_row_value(row, 4, "") or "").strip(),
                "sector_name": str(_row_value(row, 5, "") or "").strip(),
                "one_word": bool(_safe_int(_row_value(row, 6))),
                "popular": bool(_safe_int(_row_value(row, 7))),
                "sector_limit_up_count": _safe_int(_row_value(row, 8)),
                "amount": _safe_int(_row_value(row, 9)),
                "sector_amount": _safe_int(_row_value(row, 10)),
            }
        )
    return stocks


def _normalize_sector_rows(rows: list) -> list[dict]:
    sectors = []
    for row in rows:
        if not isinstance(row, list):
            continue
        name = str(_row_value(row, 1, "") or "").strip()
        if not name:
            continue
        stock_codes = [
            code.strip()
            for code in str(_row_value(row, 4, "") or "").split(",")
            if code.strip()
        ]
        sectors.append(
            {
                "sector_code": str(_row_value(row, 0, "") or "").strip(),
                "sector_name": name,
                "stock_count": _safe_int(_row_value(row, 2)),
                "amount": _safe_int(_row_value(row, 3)),
                "stock_codes": stock_codes,
            }
        )
    return sectors


def _normalize_history_rows(rows: list, category: str) -> list[dict]:
    items = []
    include_limit_details = category != "limit_down"
    for row in rows:
        if not isinstance(row, list):
            continue
        code = str(_row_value(row, 0, "") or "").strip()
        name = str(_row_value(row, 1, "") or "").strip()
        if not code or not name:
            continue
        items.append(
            {
                "code": code,
                "name": name,
                "limit_time": _format_limit_up_time(_row_value(row, 6)),
                "open_time": _format_limit_up_time(_row_value(row, 7)),
                "seal_amount": _safe_int(_row_value(row, 8)),
                "limit_tag": (
                    str(_row_value(row, 9, "") or "").strip() if include_limit_details else ""
                ),
                "limit_count": _safe_int(_row_value(row, 10)) if include_limit_details else 0,
                "themes": str(_row_value(row, 11, "") or "").strip(),
                "net_inflow": _safe_int(_row_value(row, 12)),
                "turnover": _safe_int(_row_value(row, 13)),
                "turnover_rate": parse_float(_row_value(row, 14)),
                "market_cap": _safe_int(_row_value(row, 15)),
                "reason": (
                    str(_row_value(row, 16, "") or "").strip() if include_limit_details else ""
                ),
                "seal_money": _safe_int(_row_value(row, 23)),
                "industry_id": str(_row_value(row, 26, "") or "").strip(),
                "industry_limit_up_count": (
                    _safe_int(_row_value(row, 27)) if include_limit_details else 0
                ),
            }
        )
    return items


def _normalize_sector_stock_rows(rows: list) -> list[dict]:
    stocks = []
    for row in rows:
        if not isinstance(row, list):
            continue
        code = str(_row_value(row, 0, "") or "").strip()
        name = str(_row_value(row, 1, "") or "").strip()
        if not code or not name:
            continue
        stocks.append(
            {
                "code": code,
                "name": name,
                "tags": str(_row_value(row, 4, "") or "").strip(),
                "price": parse_float(_row_value(row, 5)),
                "change_pct": parse_float(_row_value(row, 6)),
                "amount": _safe_int(_row_value(row, 7)),
                "turnover_rate": parse_float(_row_value(row, 8)),
                "float_amount": _safe_int(_row_value(row, 10)),
                "main_buy": _safe_int(_row_value(row, 11)),
                "main_sell": _safe_int(_row_value(row, 12)),
                "main_net": _safe_int(_row_value(row, 13)),
                "buy_ratio": parse_float(_row_value(row, 14)),
                "sell_ratio": parse_float(_row_value(row, 15)),
                "net_ratio": parse_float(_row_value(row, 16)),
                "limit_tag": str(_row_value(row, 23, "") or "").strip(),
                "rank_tag": str(_row_value(row, 24, "") or "").strip(),
                "recent_chg": parse_float(_row_value(row, 33)),
                "limit_count": _safe_int(_row_value(row, 40)),
                "chg_1d": parse_float(_row_value(row, 62)),
                "chg_5d": parse_float(_row_value(row, 63)),
                "chg_20d": parse_float(_row_value(row, 64)),
            }
        )
    return stocks


def _normalize_industry_rows(rows: list, start_rank: int) -> list[dict]:
    sectors: list[dict] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        code = str(_row_value(row, 0, "") or "").strip()
        name = str(_row_value(row, 1, "") or "").strip()
        if not code or not name:
            continue
        sectors.append(
            {
                "rank": start_rank + len(sectors),
                "code": code,
                "name": name,
                "change_pct": parse_float(_row_value(row, 3)),
                "amount": _safe_int(_row_value(row, 5)),
                "net_inflow": _safe_int(_row_value(row, 6)),
                "buy_amount": _safe_int(_row_value(row, 7)),
                "sell_amount": _safe_int(_row_value(row, 8)),
                "turnover_rate": parse_float(_row_value(row, 9)),
                "market_cap": _safe_int(_row_value(row, 10)),
                "avg_change": parse_float(_row_value(row, 11)),
            }
        )
    return sectors


def _payload_date(payload: dict, fallback: str) -> str:
    value = payload.get("Day") or payload.get("day") or fallback
    if isinstance(value, list):
        value = value[0] if value else fallback
    return str(value or fallback).strip()


class KaipanhongDataProvider:
    """开盘红涨停复盘数据接口。"""

    def fetch_limit_up_ladder(self, requested_date: str) -> dict:
        parsed_date = date.fromisoformat(requested_date)
        host = _REALTIME_URL if parsed_date == market_today() else _HISTORY_URL
        response = provider_post(
            host,
            data={
                **_BASE_PARAMS,
                "a": "GetZhangTingTianTi",
                "c": "FuPanLa",
                "Date": requested_date,
            },
            headers=_HEADERS,
            timeout=10,
        )
        payload = parse_text_json(response)
        if not isinstance(payload, dict) or str(payload.get("errcode")) != "0":
            message = payload.get("msg") if isinstance(payload, dict) else "响应格式无效"
            raise RuntimeError(f"开盘红涨停天梯接口异常: {message or payload}")
        stock_rows = payload.get("StockList") or []
        sector_rows = payload.get("ZhuShuList") or []
        if not isinstance(stock_rows, list) or not isinstance(sector_rows, list):
            raise RuntimeError("开盘红涨停天梯接口返回了无效列表")
        actual_date = str(payload.get("Date") or payload.get("date") or requested_date).strip()
        return {
            "date": actual_date,
            "stocks": _normalize_stock_rows(stock_rows),
            "sectors": _normalize_sector_rows(sector_rows),
        }

    def fetch_limit_history(self, requested_date: str, category: str) -> dict:
        """获取严格历史日期的涨停、跌停或风向标列表。"""
        try:
            pid_type = _HISTORY_CATEGORY_PIDS[category]
        except KeyError as error:
            raise ValueError(f"未知历史榜单类别: {category}") from error

        parsed_date = date.fromisoformat(requested_date)
        if parsed_date >= market_today():
            raise ValueError(f"开盘红历史榜单日期必须早于今天: {requested_date}")

        items: list[dict] = []
        seen_full_pages: set[str] = set()
        actual_date = requested_date
        for page_number in range(_HISTORY_MAX_PAGES):
            index = page_number * _HISTORY_PAGE_SIZE
            response = provider_post(
                _HISTORY_URL,
                data={
                    **_BASE_PARAMS,
                    "a": "HisDaBanList",
                    "c": "HisHomeDingPan",
                    "Order": "1",
                    "st": str(_HISTORY_PAGE_SIZE),
                    "Index": str(index),
                    "Is_st": "1",
                    "PidType": pid_type,
                    "Type": "6",
                    "FilterMotherboard": "0",
                    "Filter": "0",
                    "FilterTIB": "0",
                    "FilterGem": "0",
                    "Day": requested_date,
                },
                headers=_HEADERS,
                timeout=10,
            )
            payload = parse_text_json(response)
            if not isinstance(payload, dict) or str(payload.get("errcode")) != "0":
                message = (
                    payload.get("errmsg") or payload.get("msg")
                    if isinstance(payload, dict)
                    else "响应格式无效"
                )
                raise RuntimeError(f"开盘红历史榜单接口异常: {message or payload}")
            batch = payload.get("list")
            if not isinstance(batch, list):
                raise RuntimeError("开盘红历史榜单接口返回了无效列表")

            actual_date = str(payload.get("day") or requested_date).strip()
            if len(batch) == _HISTORY_PAGE_SIZE:
                signature = repr(batch)
                if signature in seen_full_pages:
                    raise RuntimeError("开盘红历史榜单接口返回了重复分页")
                seen_full_pages.add(signature)

            items.extend(_normalize_history_rows(batch, category))
            if len(batch) < _HISTORY_PAGE_SIZE:
                return {"date": actual_date, "category": category, "items": items}

        raise RuntimeError("开盘红历史榜单分页超过安全上限")

    def fetch_sector_stocks_history(self, requested_date: str, plate_id: str) -> dict:
        """获取严格历史日期的开盘红板块成分股列表。"""
        if not plate_id or not str(plate_id).strip():
            raise ValueError(f"plate_id 不能为空: {plate_id}")

        parsed_date = date.fromisoformat(requested_date)
        if parsed_date >= market_today():
            raise ValueError(f"开盘红板块成分股日期必须早于今天: {requested_date}")

        stocks: list[dict] = []
        seen_full_pages: set[str] = set()
        actual_date = requested_date
        for page_number in range(_SECTOR_STOCKS_MAX_PAGES):
            index = page_number * _SECTOR_STOCKS_PAGE_SIZE
            response = provider_post(
                _HISTORY_URL,
                data={
                    **_BASE_PARAMS,
                    "a": "ZhiShuStockList_W8",
                    "c": "ZhiShuRanking",
                    "Order": "1",
                    "st": str(_SECTOR_STOCKS_PAGE_SIZE),
                    "old": "1",
                    "Index": str(index),
                    "Date": requested_date,
                    "Type": "6",
                    "PlateID": plate_id,
                    "IsZZ": "0",
                    "IsKZZType": "0",
                    "TSZB": "0",
                    "TSZB_Type": "0",
                    "filterType": "0",
                },
                headers=_HEADERS,
                timeout=10,
            )
            payload = parse_text_json(response)
            if not isinstance(payload, dict) or str(payload.get("errcode")) != "0":
                message = (
                    payload.get("errmsg") or payload.get("msg")
                    if isinstance(payload, dict)
                    else "响应格式无效"
                )
                raise RuntimeError(f"开盘红板块成分股接口异常: {message or payload}")
            batch = payload.get("list")
            if not isinstance(batch, list):
                raise RuntimeError("开盘红板块成分股接口返回了无效列表")

            actual_date = _payload_date(payload, requested_date)
            if len(batch) == _SECTOR_STOCKS_PAGE_SIZE:
                signature = repr(batch)
                if signature in seen_full_pages:
                    raise RuntimeError("开盘红板块成分股接口返回了重复分页")
                seen_full_pages.add(signature)

            stocks.extend(_normalize_sector_stock_rows(batch))
            if len(batch) < _SECTOR_STOCKS_PAGE_SIZE:
                return {"date": actual_date, "plate_id": plate_id, "stocks": stocks}

        raise RuntimeError("开盘红板块成分股分页超过安全上限")

    def fetch_industry_rankings(self, requested_date: str) -> dict:
        """获取开盘红行业涨跌与资金排行。"""
        parsed_date = date.fromisoformat(requested_date)
        today = market_today()
        if parsed_date > today:
            raise ValueError(f"开盘红行业排行日期不能晚于今天: {requested_date}")

        host = _REALTIME_URL if parsed_date == today else _HISTORY_URL
        sectors: list[dict] = []
        seen_full_pages: set[str] = set()
        actual_date = requested_date
        for page_number in range(_HISTORY_MAX_PAGES):
            index = page_number * _HISTORY_PAGE_SIZE
            response = provider_post(
                host,
                data={
                    **_BASE_PARAMS,
                    "a": "RealRankingInfo",
                    "c": "ZhiShuRanking",
                    "Order": "1",
                    "st": str(_HISTORY_PAGE_SIZE),
                    "Index": str(index),
                    "Date": requested_date,
                    "Type": "2",
                    "ZSType": "4",
                },
                headers=_HEADERS,
                timeout=10,
            )
            payload = parse_text_json(response)
            if not isinstance(payload, dict) or str(payload.get("errcode")) != "0":
                message = (
                    payload.get("errmsg") or payload.get("msg")
                    if isinstance(payload, dict)
                    else "响应格式无效"
                )
                raise RuntimeError(f"开盘红行业排行接口异常: {message or payload}")
            batch = payload.get("list")
            if not isinstance(batch, list):
                raise RuntimeError("开盘红行业排行接口返回了无效列表")

            actual_date = _payload_date(payload, requested_date)
            if len(batch) == _HISTORY_PAGE_SIZE:
                signature = repr(batch)
                if signature in seen_full_pages:
                    raise RuntimeError("开盘红行业排行接口返回了重复分页")
                seen_full_pages.add(signature)

            sectors.extend(_normalize_industry_rows(batch, len(sectors) + 1))
            if len(batch) < _HISTORY_PAGE_SIZE:
                return {"date": actual_date, "total": len(sectors), "sectors": sectors}

        raise RuntimeError("开盘红行业排行分页超过安全上限")


kaipanhong_provider = KaipanhongDataProvider()
