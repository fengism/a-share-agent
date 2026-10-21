import hashlib
import logging
from datetime import date, datetime
from typing import Any

import pandas as pd

from app.constants.http import CLS_HEADERS
from app.core.dataframes import normalize_intraday_df
from app.core.market import contains_stock_reference, normalize_code, safe_float
from app.core.news import parse_timestamp
from app.domain.news import NewsSearchItem
from app.infrastructure.http.client import parse_text_json, provider_get

logger = logging.getLogger(__name__)

_CLS_STOCK_KLINE_URL = "https://x-quote.cls.cn/quote/stock/kline"
_CLS_STOCK_KLINE_SIGN = "d2656d0d3fdc1d489f6f316ea820cc17"
_CLS_STOCK_TIMELINE_URL = "https://x-quote.cls.cn/quote/stock/tline"
_CLS_STOCK_TIMELINE_SIGN = "afad7ec0475a1b9854313502389f3346"
_CLS_STOCK_TIMELINE_FIELDS = "date,minute,last_px,business_balance,business_amount,open_px,preclose_px,av_px"
_CLS_MARKET_EMOTION_URL = "https://x-quote.cls.cn/v2/quote/a/stock/emotion"
_CLS_MARKET_EMOTION_SIGN = "9f8797a1f4de66c2370f7a03990d2737"
_CLS_INDUSTRY_RANKINGS_URL = "https://x-quote.cls.cn/web_quote/plate/plate_list"
_CLS_INDUSTRY_RANKINGS_SIGN = "ef1ec7886be706a0b722d7e7bf3c0054"
_CLS_MARKET_WIND_URL = "https://api3.cls.cn/v2/todayTuyere"
_CLS_MARKET_WIND_STOCKS_URL = "https://x-quote.cls.cn/v2/quote/a/plate/tuyere/stocks"
_CLS_MARKET_MAINLINE_URL = "https://api3.cls.cn/v2/dingPan/mainline"
_CLS_MARKET_MAINLINE_FALLBACK_URL = "https://www.cls.cn/v2/dingPan/mainline"
_CLS_ROLL_LIST_URL = "https://www.cls.cn/v1/roll/get_roll_list"
_CLS_ROLL_LIST_FALLBACK_URL = "https://api3.cls.cn/v1/roll/get_roll_list"
_CLS_BASE = "https://www.cls.cn"
_CLS_WEB_BASE_PARAMS = {
    "app": "CailianpressWeb",
    "os": "web",
    "sv": "8.4.6",
}
_CLS_APP_BASE_PARAMS = {
    "app": "cailianpress",
    "sv": "8.7.4",
    "os": "android",
    "mb": "Xiaomi-2206123SC",
    "ov": "32",
    "channel": "8",
    "motif": "0",
    "net": "",
    "province_code": "3205",
    "token": "",
    "uid": "",
}
_CLS_APP_HEADERS = {
    "User-Agent": "okhttp/4.9.0",
    "Accept-Encoding": "gzip",
    "Connection": "Keep-Alive",
}
_CLS_KLINE_PAGE_SIZE = 1000
_CLS_KLINE_MAX_PAGES = 20
_CLS_KLINE_TYPE_MAP = {
    "daily": "fd1",
    "weekly": "fw",
    "monthly": "fm",
}
_CLS_KLINE_COLUMNS = ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "换手率", "涨跌幅", "昨收"]


def _parse_kline_date(value: str) -> date:
    for date_format in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"无效 K 线日期: {value}")


def _empty_kline_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=_CLS_KLINE_COLUMNS)


def _numeric_column(frame: pd.DataFrame, name: str) -> pd.Series:
    if name not in frame.columns:
        return pd.Series(index=frame.index, dtype="float64")
    return pd.to_numeric(frame[name], errors="coerce")


def _normalize_kline_rows(rows: list[dict], start_date: date, end_date: date) -> pd.DataFrame:
    if not rows:
        return _empty_kline_frame()

    frame = pd.DataFrame(rows)
    if "date" not in frame.columns:
        return _empty_kline_frame()
    trade_dates = pd.to_datetime(frame["date"].astype(str), format="%Y%m%d", errors="coerce")
    normalized = pd.DataFrame(index=frame.index)
    normalized["日期"] = trade_dates
    normalized["开盘"] = _numeric_column(frame, "open_px")
    normalized["收盘"] = _numeric_column(frame, "close_px")
    normalized["最高"] = _numeric_column(frame, "high_px")
    normalized["最低"] = _numeric_column(frame, "low_px")
    # 财联社 business_amount 原始单位为股；统一历史日线契约使用股。
    normalized["成交量"] = _numeric_column(frame, "business_amount")
    normalized["成交额"] = _numeric_column(frame, "business_balance")
    normalized["振幅"] = (_numeric_column(frame, "amp") * 100).round(6)
    normalized["换手率"] = (_numeric_column(frame, "tr") * 100).round(6)
    normalized["涨跌幅"] = (_numeric_column(frame, "change") * 100).round(6)
    normalized["昨收"] = _numeric_column(frame, "preclose_px")
    normalized = normalized[
        normalized["日期"].notna()
        & (normalized["日期"].dt.date >= start_date)
        & (normalized["日期"].dt.date <= end_date)
    ]
    normalized = normalized.sort_values("日期").drop_duplicates(subset=["日期"], keep="last")
    normalized["日期"] = normalized["日期"].dt.strftime("%Y-%m-%d")
    return normalized.reset_index(drop=True).reindex(columns=_CLS_KLINE_COLUMNS)


def _timeline_timestamp(trade_date: object, minute: object) -> str | None:
    try:
        parsed_date = _parse_kline_date(str(trade_date))
        minute_text = str(int(float(str(minute)))).zfill(4)
        parsed_time = datetime.strptime(minute_text, "%H%M").time()
    except (TypeError, ValueError):
        return None
    return datetime.combine(parsed_date, parsed_time).strftime("%Y-%m-%d %H:%M")


def _normalize_timeline_rows(rows: list[dict], requested_date: date | None) -> pd.DataFrame:
    normalized_rows = []
    for row in rows:
        timestamp = _timeline_timestamp(row.get("date"), row.get("minute"))
        if timestamp is None:
            continue
        trade_date = datetime.strptime(timestamp[:10], "%Y-%m-%d").date()
        if requested_date is not None and trade_date != requested_date:
            continue
        normalized_rows.append(
            {
                "time": timestamp,
                "price": row.get("last_px"),
                "avg_price": row.get("av_px"),
                "volume": row.get("business_amount"),
                "amount": row.get("business_balance"),
            }
        )
    if not normalized_rows:
        return pd.DataFrame()
    frame = pd.DataFrame(normalized_rows)
    for column in ("price", "avg_price", "volume", "amount"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["price"] = frame["price"].round(6)
    frame["avg_price"] = frame["avg_price"].round(6)
    frame = frame.dropna(subset=["time", "price"]).sort_values("time")
    frame = frame.drop_duplicates(subset=["time"], keep="last").reset_index(drop=True)
    return normalize_intraday_df(frame)


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None


def _percentage_value(value: object) -> float | None:
    text = str(value).strip()
    has_percent_suffix = text.endswith("%")
    raw = safe_float(text.removesuffix("%"))
    if raw is None:
        return None
    numeric = float(raw)
    if has_percent_suffix or abs(numeric) > 1:
        return round(numeric, 6)
    return round(numeric * 100, 6)


def _cls_app_params(**extra: str) -> dict[str, str]:
    params = {**_CLS_APP_BASE_PARAMS, **extra}
    serialized = "&".join(f"{key}={value}" for key, value in sorted(params.items()))
    sha1_digest = hashlib.sha1(serialized.encode()).hexdigest()
    params["sign"] = hashlib.md5(sha1_digest.encode()).hexdigest()
    return params


def _cls_web_params(**extra: object) -> dict[str, str]:
    """生成财联社 web 端查询参数（含 md5(sha1(sorted k=v)) 签名）。"""
    params = {**_CLS_WEB_BASE_PARAMS, **{key: str(value) for key, value in extra.items()}}
    serialized = "&".join(f"{key}={value}" for key, value in sorted(params.items()))
    params["sign"] = hashlib.md5(hashlib.sha1(serialized.encode()).hexdigest().encode()).hexdigest()
    return params


def _normalize_emotion_distribution(value: object) -> dict:
    data = value if isinstance(value, dict) else {}
    normalized: dict[str, Any] = {"status": bool(data.get("status", False))}
    for field in (
        "suspend_num",
        "up_num",
        "down_num",
        "rise_num",
        "fall_num",
        "flat_num",
        "down_10",
        "down_8",
        "down_6",
        "down_4",
        "down_2",
        "up_2",
        "up_4",
        "up_6",
        "up_8",
        "up_10",
    ):
        normalized[field] = _optional_int(data.get(field)) or 0
    return normalized


def _normalize_limit_up_board(value: object) -> list[dict]:
    data = value if isinstance(value, dict) else {}
    row1 = data.get("row1")
    labels = row1 if isinstance(row1, list) else []
    row2 = data.get("row2")
    counts = row2 if isinstance(row2, list) else []
    row3 = data.get("row3")
    rates = row3 if isinstance(row3, list) else []
    board_items = []
    for index, label in enumerate(labels):
        name = str(label or "").strip()
        if not name:
            continue
        rate = rates[index + 1] if index + 1 < len(rates) else None
        board_items.append(
            {
                "name": name,
                "count": _optional_int(counts[index] if index < len(counts) else None) or 0,
                "promotion_rate": str(rate).strip() if rate not in (None, "") else None,
            }
        )
    return board_items


def _normalize_mainline_faucet(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    raw_code = str(value.get("stock_code") or "").strip()
    code = raw_code[2:] if raw_code[:2].lower() in {"sh", "sz"} else raw_code
    name = str(value.get("stock_name") or "").strip()
    if not code or not name:
        return None
    return {
        "code": code,
        "name": name,
        "change_pct": safe_float(value.get("rise_range")),
        "reason": str(value.get("reason") or "").strip(),
    }


def _normalize_mainline_plate(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    name = str(value.get("name") or "").strip()
    if not name:
        return None
    faucets = []
    for key in ("faucet_1", "faucet_2", "faucet_3"):
        faucet = _normalize_mainline_faucet(value.get(key))
        if faucet is not None:
            faucets.append(faucet)
    article_raw = value.get("article")
    article = article_raw if isinstance(article_raw, dict) else {}
    change = safe_float(value.get("rise_range"))
    return {
        "code": str(value.get("code") or "").strip(),
        "name": name,
        "reason": str(value.get("reason") or "").strip(),
        "rise_count": _optional_int(value.get("rise_count")),
        "change_pct": round(change * 100, 6) if change is not None else None,
        "article_title": str(article.get("title") or "").strip(),
        "faucets": faucets,
    }


def _normalize_mainline_chances(chances: list) -> list[dict]:
    normalized = []
    for chance in chances:
        if not isinstance(chance, dict):
            continue
        title = str(chance.get("title") or "").strip()
        if not title:
            continue
        plates = chance.get("plates")
        plate_rows = plates if isinstance(plates, list) else []
        normalized.append(
            {
                "title": title,
                "description": str(chance.get("mainLine_desc") or "").strip(),
                "continued_days": _optional_int(chance.get("continued")),
                "hot": _optional_int(chance.get("hot")),
                "plates": [
                    plate
                    for plate in (
                        _normalize_mainline_plate(plate_row)
                        for plate_row in plate_rows
                    )
                    if plate is not None
                ],
            }
        )
    return normalized


def _normalize_mainline_style_index(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    raw_code = str(value.get("code") or "").strip()
    code = raw_code[2:] if raw_code[:2].lower() in {"sh", "sz"} else raw_code
    stocks = []
    for stack in value.get("stacks") or []:
        if not isinstance(stack, dict):
            continue
        raw_stock_code = str(stack.get("stock_code") or "").strip()
        stock_code = (
            raw_stock_code[2:] if raw_stock_code[:2].lower() in {"sh", "sz"} else raw_stock_code
        )
        stock_name = str(stack.get("stock_name") or "").strip()
        if not stock_code or not stock_name:
            continue
        stocks.append(
            {
                "code": stock_code,
                "name": stock_name,
                "change_30d": _percentage_value(stack.get("rise_range")),
            }
        )
    return {
        "code": code,
        "name": str(value.get("name") or "").strip(),
        "change_30d": _percentage_value(value.get("change30")),
        "stocks": stocks,
    }


def _normalize_mainline_style(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    indexes = [
        index
        for index in (
            _normalize_mainline_style_index(value.get(key))
            for key in ("index_1", "index_2")
        )
        if index is not None
    ]
    if not indexes and not str(value.get("title") or "").strip():
        return None
    return {
        "title": str(value.get("title") or "").strip(),
        "interpret": str(value.get("interpret") or "").strip(),
        "indexes": indexes,
    }


class ClsDataProvider:
    """Purpose: 封装财联社新闻、市场情绪与不复权股票行情接口。"""

    name = "cls"

    def fetch_stock_intraday_minute(self, code: str, date: str | None = None) -> pd.DataFrame:
        """获取财联社最新交易日个股分时数据。"""
        response = provider_get(
            _CLS_STOCK_TIMELINE_URL,
            params={
                "app": "CailianpressWeb",
                "os": "web",
                "sv": "8.4.6",
                "secu_code": normalize_code(code).prefixed_lower,
                "fields": _CLS_STOCK_TIMELINE_FIELDS,
                "sign": _CLS_STOCK_TIMELINE_SIGN,
            },
            headers=CLS_HEADERS,
            timeout=10,
        )
        payload = parse_text_json(response)
        if not isinstance(payload, dict) or payload.get("code") != 200:
            message = payload.get("msg") if isinstance(payload, dict) else "响应格式无效"
            raise RuntimeError(f"财联社分时接口异常: {message}")
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            raise RuntimeError("财联社分时接口返回了无效 data")
        rows = data.get("line") or []
        if not isinstance(rows, list):
            raise RuntimeError("财联社分时接口返回了无效 line")
        requested_date = _parse_kline_date(date) if date else None
        return _normalize_timeline_rows(
            [row for row in rows if isinstance(row, dict)],
            requested_date,
        )

    def _fetch_stock_kline_page(self, code: str, period: str, *, limit: int, offset: int) -> list[dict]:
        response = provider_get(
            _CLS_STOCK_KLINE_URL,
            params={
                "app": "CailianpressWeb",
                "os": "web",
                "sv": "8.4.6",
                "secu_code": normalize_code(code).prefixed_lower,
                "type": _CLS_KLINE_TYPE_MAP[period],
                "limit": limit,
                "offset": offset,
                "sign": _CLS_STOCK_KLINE_SIGN,
            },
            headers=CLS_HEADERS,
            timeout=10,
        )
        payload = parse_text_json(response)
        if not isinstance(payload, dict) or payload.get("code") != 200:
            message = payload.get("msg") if isinstance(payload, dict) else "响应格式无效"
            raise RuntimeError(f"财联社 K 线接口异常: {message}")
        rows = payload.get("data") or []
        if not isinstance(rows, list):
            raise RuntimeError("财联社 K 线接口返回了无效 data")
        return [row for row in rows if isinstance(row, dict)]

    def fetch_stock_kline(
        self,
        code: str,
        period: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame:
        """获取指定日期区间的财联社不复权股票 K 线。"""
        if adjust:
            raise ValueError("财联社 K 线不支持复权")
        if period not in _CLS_KLINE_TYPE_MAP:
            raise ValueError(f"财联社 K 线不支持周期: {period}")
        parsed_start_date = _parse_kline_date(start_date)
        parsed_end_date = _parse_kline_date(end_date)
        if parsed_start_date > parsed_end_date:
            raise ValueError("start_date 不能晚于 end_date")

        rows: list[dict] = []
        offset = 0
        for _ in range(_CLS_KLINE_MAX_PAGES):
            page = self._fetch_stock_kline_page(
                code,
                period,
                limit=_CLS_KLINE_PAGE_SIZE,
                offset=offset,
            )
            if not page:
                break
            rows.extend(page)
            page_dates = [
                parsed_date
                for row in page
                if row.get("date") is not None
                for parsed_date in [_parse_kline_date(str(row["date"]))]
            ]
            if page_dates and min(page_dates) <= parsed_start_date:
                break
            if len(page) < _CLS_KLINE_PAGE_SIZE:
                break
            offset += len(page)
        else:
            raise RuntimeError("财联社 K 线分页超过安全上限")

        return _normalize_kline_rows(rows, parsed_start_date, parsed_end_date)

    def fetch_market_emotion(self) -> dict:
        """获取财联社实时市场情绪数据。"""
        response = provider_get(
            _CLS_MARKET_EMOTION_URL,
            params={
                "app": "CailianpressWeb",
                "os": "web",
                "sv": "8.4.6",
                "sign": _CLS_MARKET_EMOTION_SIGN,
            },
            headers=CLS_HEADERS,
            timeout=10,
        )
        payload = parse_text_json(response)
        if not isinstance(payload, dict) or payload.get("code") != 200:
            message = payload.get("msg") if isinstance(payload, dict) else "响应格式无效"
            raise RuntimeError(f"财联社市场情绪接口异常: {message}")
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            raise RuntimeError("财联社市场情绪接口返回了无效 data")
        return {
            "market_degree": _optional_int(data.get("market_degree")),
            "shsz_balance": str(data.get("shsz_balance") or ""),
            "shsz_balance_change_px": str(data.get("shsz_balance_change_px") or ""),
            "preview_balance": str(data.get("preview_balance") or ""),
            "preview_balance_change_px": str(data.get("preview_balance_change_px") or ""),
            "up_ratio": str(data.get("up_ratio") or ""),
            "up_ratio_num": _optional_int(data.get("up_ratio_num")),
            "up_open_num": _optional_int(data.get("up_open_num")),
            "performance": str(data.get("performance") or ""),
            "up_open_ratio": str(data.get("up_open_ratio") or ""),
            "profit_ratio": str(data.get("profit_ratio") or ""),
            "up_down_dis": _normalize_emotion_distribution(data.get("up_down_dis")),
            "limit_up_board": _normalize_limit_up_board(data.get("limit_up_board")),
        }

    def fetch_industry_rankings(self, top_n: int = 50) -> dict:
        """获取财联社行业板块涨跌幅排名。"""
        response = provider_get(
            _CLS_INDUSTRY_RANKINGS_URL,
            params={
                "app": "CailianpressWeb",
                "os": "web",
                "page": 5,
                "rever": 1,
                "sv": "8.4.6",
                "type": "industry",
                "way": "change",
                "sign": _CLS_INDUSTRY_RANKINGS_SIGN,
            },
            headers=CLS_HEADERS,
            timeout=10,
        )
        payload = parse_text_json(response)
        if not isinstance(payload, dict) or payload.get("code") != 200:
            message = payload.get("msg") if isinstance(payload, dict) else "响应格式无效"
            raise RuntimeError(f"财联社行业板块接口异常: {message}")
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            raise RuntimeError("财联社行业板块接口返回了无效 data")
        plate_data = data.get("plate_data") or []
        if not isinstance(plate_data, list):
            raise RuntimeError("财联社行业板块接口返回了无效 plate_data")

        rows: list[dict[str, Any]] = []
        for item in plate_data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("secu_name") or "").strip()
            if not name:
                continue
            first_stock_raw = item.get("first_stock")
            first_stock = first_stock_raw if isinstance(first_stock_raw, dict) else {}
            change = safe_float(item.get("change"))
            leader_change = safe_float(first_stock.get("change"))
            rows.append(
                {
                    "rank": 0,
                    "name": name,
                    "change_pct": round(change * 100, 6) if change is not None else None,
                    "code": str(item.get("secu_code") or "").strip(),
                    "up_count": _optional_int(item.get("limit_up")),
                    "down_count": _optional_int(item.get("limit_down")),
                    "leader": str(first_stock.get("secu_name") or "").strip(),
                    "leader_change": round(leader_change * 100, 6) if leader_change is not None else None,
                }
            )

        rows.sort(
            key=lambda row: row["change_pct"] if row["change_pct"] is not None else float("-inf"),
            reverse=True,
        )
        for rank, row in enumerate(rows, start=1):
            row["rank"] = rank
        limit = max(0, int(top_n))
        return {
            "top": rows[:limit],
            "bottom": rows[-limit:] if limit else [],
            "total": len(rows),
        }

    def fetch_market_wind(self) -> list[dict]:
        """获取财联社今日风口板块。"""
        response = provider_get(
            _CLS_MARKET_WIND_URL,
            params=_cls_app_params(),
            headers={**_CLS_APP_HEADERS, "Host": "api3.cls.cn"},
            timeout=10,
        )
        payload = parse_text_json(response)
        if not isinstance(payload, dict) or payload.get("errno") != 0:
            message = payload.get("msg") if isinstance(payload, dict) else "响应格式无效"
            raise RuntimeError(f"财联社今日风口接口异常: {message or payload}")
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            raise RuntimeError("财联社今日风口接口返回了无效 data")
        items = data.get("today_tuyere") or []
        if not isinstance(items, list):
            raise RuntimeError("财联社今日风口接口返回了无效 today_tuyere")
        return [
            {
                "plate_code": str(item.get("plate_code") or "").strip(),
                "plate_name": str(item.get("title") or "").strip(),
                "catalyst": str(item.get("interpret") or "").strip(),
            }
            for item in items
            if isinstance(item, dict) and str(item.get("plate_code") or "").strip()
        ]

    def fetch_market_wind_stocks(self, plate_code: str) -> list[dict]:
        """获取指定风口板块的龙头股。"""
        normalized_plate_code = plate_code.strip()
        if not normalized_plate_code:
            raise ValueError("plate_code 不能为空")
        response = provider_get(
            _CLS_MARKET_WIND_STOCKS_URL,
            params=_cls_app_params(plate_code=normalized_plate_code),
            headers={**_CLS_APP_HEADERS, "Host": "x-quote.cls.cn"},
            timeout=10,
        )
        payload = parse_text_json(response)
        if not isinstance(payload, dict) or payload.get("code") != 200:
            message = payload.get("msg") if isinstance(payload, dict) else "响应格式无效"
            raise RuntimeError(f"财联社风口龙头股接口异常: {message or payload}")
        items = payload.get("data") or []
        if not isinstance(items, list):
            raise RuntimeError("财联社风口龙头股接口返回了无效 data")

        stocks = []
        for item in items:
            if not isinstance(item, dict):
                continue
            raw_code = str(item.get("ori_code") or item.get("secu_code") or "").strip()
            code = raw_code[2:] if raw_code[:2].lower() in {"sh", "sz"} else raw_code
            stocks.append(
                {
                    "code": code,
                    "name": str(item.get("secu_name") or "").strip(),
                    "price": safe_float(item.get("last_px")),
                    "change_pct": _percentage_value(item.get("change")),
                    "limit_up_days": _optional_int(item.get("limit_up_days", item.get("continuous"))) or 0,
                }
            )
        return stocks

    def fetch_market_mainline(self) -> dict:
        """获取财联社今日主线机会。"""
        endpoints = (
            (_CLS_MARKET_MAINLINE_URL, "api3.cls.cn"),
            (_CLS_MARKET_MAINLINE_FALLBACK_URL, "www.cls.cn"),
        )
        response = None
        last_exc: Exception | None = None
        for endpoint, host in endpoints:
            try:
                response = provider_get(
                    endpoint,
                    params=_cls_app_params(),
                    headers={**_CLS_APP_HEADERS, "Host": host},
                    timeout=5,
                )
                break
            except Exception as exc:
                last_exc = exc
                logger.info("财联社主线端点 %s 请求失败: %s，尝试备用端点", endpoint, exc)
        if response is None:
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("财联社主线接口无响应")
        payload = parse_text_json(response)
        if not isinstance(payload, dict) or payload.get("errno") != 0:
            message = payload.get("msg") if isinstance(payload, dict) else "响应格式无效"
            raise RuntimeError(f"财联社主线接口异常: {message or payload}")
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            raise RuntimeError("财联社主线接口返回了无效 data")
        chances = data.get("chances")
        if not isinstance(chances, list):
            raise RuntimeError("财联社主线接口返回了无效 chances")
        return {
            "chances": _normalize_mainline_chances(chances),
            "style": _normalize_mainline_style(data.get("styles")),
        }

    def fetch_market_kuaixun(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        """获取财联社 7×24 电报快讯。

        Param:
            code: 可选，股票代码，用于过滤相关新闻
            code_name: 可选，股票名称，用于过滤相关新闻
        Return:
            list[NewsSearchItem]: 快讯列表
        """
        response = None
        last_exc: Exception | None = None
        for endpoint in (_CLS_ROLL_LIST_URL, _CLS_ROLL_LIST_FALLBACK_URL):
            try:
                response = provider_get(
                    endpoint,
                    params=_cls_web_params(category="", last_time="", rn=50),
                    headers=CLS_HEADERS,
                    timeout=5,
                )
                break
            except Exception as exc:
                last_exc = exc
                logger.info("财联社快讯端点 %s 请求失败: %s，尝试备用端点", endpoint, exc)
        if response is None:
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("财联社电报接口无响应")
        payload = parse_text_json(response)
        if not isinstance(payload, dict) or payload.get("errno") != 0:
            message = payload.get("msg") if isinstance(payload, dict) else "响应格式无效"
            raise RuntimeError(f"财联社电报接口异常: {message or payload}")
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            raise RuntimeError("财联社电报接口返回了无效 data")
        rows = data.get("roll_data") or []
        if not isinstance(rows, list):
            raise RuntimeError("财联社电报接口返回了无效 roll_data")
        results: list[NewsSearchItem] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            # 跳过广告与已下线/未入流的条目
            if item.get("is_ad"):
                continue
            if item.get("in_roll") not in (None, 1) or item.get("status") not in (None, 1):
                continue
            brief = str(item.get("brief") or "").strip()
            title = str(item.get("title") or "").strip() or brief
            content = str(item.get("content") or "").strip() or brief
            # 短电报 brief 与 content 相同，避免前端标题与正文重复展示。
            if content == title:
                content = ""
            if not title and not content:
                continue
            if (code_name or code) and not contains_stock_reference(f"{title}\n{content}", code, code_name):
                continue
            raw_id = str(item.get("id") or "").strip()
            url = str(item.get("shareurl") or "").strip() or (f"{_CLS_BASE}/detail/{raw_id}" if raw_id else "")
            image_url = str(item.get("img") or "").strip()
            if not image_url:
                images = item.get("images")
                if isinstance(images, list):
                    image_url = next((str(url).strip() for url in images if str(url).strip()), "")
            if image_url and not image_url.startswith(("http://", "https://")):
                image_url = ""
            publish_time = parse_timestamp(item.get("ctime"))
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content[:500],
                    source="财联社7×24快讯",
                    publish_time=publish_time.isoformat(sep=" ") if publish_time else "",
                    url=url,
                    author=str(item.get("author") or "").strip(),
                    read_count=_optional_int(item.get("reading_num")) or 0,
                    comment_count=_optional_int(item.get("comment_num")) or 0,
                    image_url=image_url,
                )
            )
        return results

    def fetch_market_news(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        """财联社头条新闻。

        Param:
            code: 可选，6 位股票代码
            code_name: 可选，股票名称
        Return:
            财联社头条 NewsSearchItem 列表
        """
        try:
            params = {
                "app": "CailianpressWeb",
                "os": "web",
                "sv": "8.4.6",
                "sign": "9f8797a1f4de66c2370f7a03990d2737",
            }
            response = provider_get(
                "https://www.cls.cn/v3/depth/home/assembled/1000",
                params=params,
                headers=CLS_HEADERS,
                timeout=10,
            )

            data = parse_text_json(response).get("data", {})
            top_articles = data.get("top_article", []) or []
            articles = data.get("depth_list", []) or []
            articles = top_articles + articles
            results: list[NewsSearchItem] = []
            for item in articles:
                title = str(item.get("title") or "").strip()
                article_rec = item.get("article_rec", [])
                content = ""
                for rec in article_rec:
                    content += str(rec.get("brief") or "").strip()
                if content == "":
                   content = str(item.get("brief") or "").strip()
                if content == "":
                    continue
                combined = f"{title}\n{content}"
                if (code_name or code) and not contains_stock_reference(combined, code, code_name):
                    continue
                publish_time = parse_timestamp(item.get("ctime") or item.get("time") or item.get("created_at"))
                results.append(
                    NewsSearchItem(
                        title=title,
                        content=content[:500],
                        source=item.get("source", "财联社头条"),
                        publish_time=publish_time.isoformat(sep=" ") if publish_time else "",
                        url=item.get("external_link", ""),
                        author=item.get("author", ""),
                        read_count=int(item.get("read_count", 0)),
                        comment_count=int(item.get("comment_count", 0)),
                    )
                )
            return results
        except Exception as e:
            logger.warning(f"财联社头条获取失败: {e}")
            return []

cls_provider = ClsDataProvider()
