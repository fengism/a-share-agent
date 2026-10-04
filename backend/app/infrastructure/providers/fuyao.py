"""fuyao（同花顺金融数据 API）兜底数据源。

覆盖涨跌停/炸板与估值两类接口，作为主数据源不可用时的第二顺位：
  - GET /api/a-share/special-data/limit-up-pool      涨停股票池
  - GET /api/a-share/special-data/limit-down-pool    跌停股票池
  - GET /api/a-share/special-data/limit-break-pool   炸板股票池
  - GET /api/a-share/special-data/limit-up-ladder    连板天梯（近 30 个交易日）
  - GET /api/a-share/valuations/snapshot            批量估值快照（PE/PB/PS/PCF）

接口约定：HTTP 状态码恒为 200，业务错误通过响应体 code 字段表达（code=0 成功）。
鉴权走请求头 X-api-key，密钥读取 Settings.fuyao_api_key（.env 或后台配置）。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.configuration import get_settings
from app.core.market import normalize_code
from app.infrastructure.http.client import provider_get

_BASE_URL = "https://fuyao.aicubes.cn"
_SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")
_TIMEOUT_SECONDS = 10
_PAGE_SIZE = 200
_MAX_PAGES = 20

_LIMIT_UP_POOL_PATH = "/api/a-share/special-data/limit-up-pool"
_LIMIT_DOWN_POOL_PATH = "/api/a-share/special-data/limit-down-pool"
_LIMIT_BREAK_POOL_PATH = "/api/a-share/special-data/limit-break-pool"
_VALUATION_SNAPSHOT_PATH = "/api/a-share/valuations/snapshot"
_PRICE_SNAPSHOT_PATH = "/api/a-share/prices/snapshot"
# 快照接口同样按 100 个代码分批，避免触发 code=1003
_SNAPSHOT_BATCH_SIZE = 100
# 服务端对单次请求的 thscodes 数量上限为 100，超出返回 code=1003
_VALUATION_BATCH_SIZE = 100
_LIMIT_UP_LADDER_PATH = "/api/a-share/special-data/limit-up-ladder"

_POOL_SORT_FIELDS = {
    _LIMIT_UP_POOL_PATH: "seal_money",
    _LIMIT_DOWN_POOL_PATH: "last_limit_time",
    _LIMIT_BREAK_POOL_PATH: "open_times",
}


class FuyaoNotConfiguredError(RuntimeError):
    """未配置fuyao API Key，无法调用fuyao接口。"""


def _date_ms(target: date) -> int:
    """交易日对应的 Asia/Shanghai 零点毫秒时间戳。"""
    from datetime import datetime

    moment = datetime.combine(target, datetime.min.time(), _SHANGHAI_TIMEZONE)
    return int(moment.timestamp() * 1000)


def _safe_int(value: object) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: object) -> float | None:
    try:
        text = str(value).replace(",", "").strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _normalize_time(value: object) -> str:
    """fuyao返回 HH:MM，统一补成 HH:MM:SS 以对齐开盘红格式。"""
    text = str(value or "").strip()
    if not text:
        return ""
    parts = text.split(":")
    if len(parts) == 2 and all(part.isdigit() for part in parts):
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}:00"
    return text


def _thousand_yuan_to_yuan(value: object) -> int:
    """封单额等金额统一取整为元。"""
    amount = _safe_float(value)
    return int(round(amount)) if amount is not None else 0


class FuyaoDataProvider:
    """fuyao涨跌停与炸板接口。"""

    def _headers(self) -> dict[str, str]:
        api_key = (get_settings().fuyao_api_key or "").strip()
        if not api_key:
            raise FuyaoNotConfiguredError("fuyao API Key 未配置")
        return {
            "X-api-key": api_key,
            "Accept": "application/json",
            "User-Agent": "a-share-agent/1.0 (+fuyao-fallback)",
        }

    def _get_data(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = provider_get(
            f"{_BASE_URL}{path}",
            params=params or {},
            headers=self._headers(),
            timeout=_TIMEOUT_SECONDS,
        )
        try:
            payload = response.json()
        except ValueError as error:
            raise RuntimeError(f"fuyao接口返回了非 JSON 内容: {path}") from error
        if not isinstance(payload, dict):
            raise RuntimeError(f"fuyao接口响应格式无效: {path}")
        code = payload.get("code")
        if code != 0:
            message = payload.get("message") or payload.get("msg") or payload
            raise RuntimeError(f"fuyao接口异常: code={code}, message={message}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise RuntimeError(f"fuyao接口缺少 data 字段: {path}")
        return data

    def _get_pool_items(
        self,
        path: str,
        requested_date: str,
        sort_field: str,
    ) -> list[dict[str, Any]]:
        """按分页拉完整个股票池明细。"""
        target = date.fromisoformat(requested_date)
        items: list[dict[str, Any]] = []
        for page in range(1, _MAX_PAGES + 1):
            data = self._get_data(
                path,
                {
                    "date_ms": _date_ms(target),
                    "page": page,
                    "size": _PAGE_SIZE,
                    "sort_field": sort_field,
                    "sort_dir": "desc",
                },
            )
            pagination = data.get("pagination") or {}
            batch = data.get("item") or []
            if not isinstance(batch, list):
                raise RuntimeError(f"fuyao接口返回了无效列表: {path}")
            items.extend(item for item in batch if isinstance(item, dict))
            total = _safe_int(pagination.get("total"))
            pages = _safe_int(pagination.get("pages"))
            if pages:
                if page >= pages:
                    break
            elif total:
                if len(items) >= total:
                    break
            elif len(batch) < _PAGE_SIZE:
                # 上游未给分页元信息时，按短页兜底判断。
                break
        return items

    # ------------------------------------------------------------------ 涨停池

    def fetch_limit_up_pool(self, requested_date: str) -> dict:
        items = self._get_pool_items(_LIMIT_UP_POOL_PATH, requested_date, _POOL_SORT_FIELDS[_LIMIT_UP_POOL_PATH])
        return {
            "date": requested_date,
            "category": "limit_up",
            "items": [_normalize_limit_up_item(item) for item in items],
        }

    # ------------------------------------------------------------------ 跌停池

    def fetch_limit_down_pool(self, requested_date: str) -> dict:
        items = self._get_pool_items(_LIMIT_DOWN_POOL_PATH, requested_date, _POOL_SORT_FIELDS[_LIMIT_DOWN_POOL_PATH])
        return {
            "date": requested_date,
            "category": "limit_down",
            "items": [_normalize_limit_down_item(item) for item in items],
        }

    # ------------------------------------------------------------------ 炸板池

    def fetch_limit_break_pool(self, requested_date: str) -> dict:
        items = self._get_pool_items(_LIMIT_BREAK_POOL_PATH, requested_date, _POOL_SORT_FIELDS[_LIMIT_BREAK_POOL_PATH])
        return {
            "date": requested_date,
            "category": "limit_break",
            "items": [_normalize_limit_break_item(item) for item in items],
        }

    # ---------------------------------------------------------------- 行情快照

    def fetch_quote_snapshot(self, thscodes: list[str]) -> dict:
        """批量查询行情快照，返回 {6位代码: 统一 quote 结构}。

        上游不返回中文名，name 留空由上层用代码表补齐。
        """
        codes = [code.strip().upper() for code in thscodes if code and code.strip()]
        deduped = list(dict.fromkeys(codes))
        quotes: dict[str, dict[str, Any]] = {}
        timestamp: int | None = None
        for index in range(0, len(deduped), _SNAPSHOT_BATCH_SIZE):
            batch = deduped[index : index + _SNAPSHOT_BATCH_SIZE]
            data = self._get_data(
                _PRICE_SNAPSHOT_PATH,
                {"thscodes": ",".join(batch)},
            )
            items = data.get("item")
            if items is not None and not isinstance(items, list):
                raise RuntimeError("fuyao 行情快照接口返回了无效列表")
            batch_timestamp = _safe_int(data.get("timestamp"))
            timestamp = batch_timestamp if timestamp is None else max(timestamp, batch_timestamp)
            for item in items or []:
                if not isinstance(item, dict):
                    continue
                quote = _normalize_quote_snapshot_item(item, batch_timestamp)
                if quote["code"]:
                    quotes.setdefault(quote["code"], quote)
        return {"quotes": quotes, "timestamp": timestamp or None}

    def fetch_stock_quotes(self, codes: list[str]) -> dict[str, dict[str, Any]]:
        """与腾讯/tdxhub 同签名的批量实时行情，供兜底链直接调用。"""
        thscodes = [f"{normalize_code(code).raw}.{normalize_code(code).exchange}" for code in codes]
        return self.fetch_quote_snapshot(thscodes)["quotes"]

    # ---------------------------------------------------------------- 估值快照

    def fetch_valuation_snapshot(self, thscodes: list[str]) -> dict:
        """批量查询最新估值快照，按请求顺序返回。

        服务端单次上限 100 个代码，这里自动分批；上游未返回的代码不生成占位项。
        """
        codes = [code.strip().upper() for code in thscodes if code and code.strip()]
        deduped = list(dict.fromkeys(codes))
        items: list[dict[str, Any]] = []
        timestamp: int | None = None
        for index in range(0, len(deduped), _VALUATION_BATCH_SIZE):
            batch = deduped[index : index + _VALUATION_BATCH_SIZE]
            data = self._get_data(
                _VALUATION_SNAPSHOT_PATH,
                {"thscodes": ",".join(batch)},
            )
            batch_items = data.get("item")
            if batch_items is not None and not isinstance(batch_items, list):
                raise RuntimeError("fuyao 估值接口返回了无效列表")
            items.extend(_normalize_valuation_item(item) for item in (batch_items or []) if isinstance(item, dict))
            batch_timestamp = _safe_int(data.get("timestamp"))
            timestamp = batch_timestamp if timestamp is None else max(timestamp, batch_timestamp)
        return {"items": items, "timestamp": timestamp or None}

    # ---------------------------------------------------------------- 连板天梯

    def fetch_limit_up_ladder(self, requested_date: str) -> dict:
        """涨停天梯。

        fuyao的连板天梯接口只返回近 30 个交易日、每板位最多 4 只，属于有损摘要；
        这里以涨停池（全量）为主，连板天梯接口仅用于补齐 2 板及以上股票的连板天数。
        fuyao没有板块维度，因此 sectors 留空，涨停原因挂到个股的 sector_name 上。
        """
        pool_items = self._get_pool_items(_LIMIT_UP_POOL_PATH, requested_date, _POOL_SORT_FIELDS[_LIMIT_UP_POOL_PATH])
        stocks = [_normalize_ladder_item(item) for item in pool_items]
        for stock in self._fetch_ladder_board_stocks(requested_date):
            # 天梯接口给出的是权威连板天数，涨停池缺失时用它补齐。
            matched = next((item for item in stocks if item["code"] == stock["code"]), None)
            if matched is not None and matched["board_count"] < stock["board_count"]:
                matched["board_count"] = stock["board_count"]
        return {
            "date": requested_date,
            "stocks": stocks,
            "sectors": [],
        }

    def _fetch_ladder_board_stocks(self, requested_date: str) -> list[dict[str, Any]]:
        """连板天梯接口：只用于补 2 板及以上股票，返回空表示不覆盖涨停池结果。"""
        try:
            data = self._get_data(_LIMIT_UP_LADDER_PATH)
        except Exception:
            return []
        wanted = requested_date.replace("-", "")
        stocks: list[dict[str, Any]] = []
        for day_entry in data.get("item") or []:
            if not isinstance(day_entry, dict):
                continue
            day_text = str(day_entry.get("date") or "")
            if day_text and wanted and day_text != wanted:
                continue
            boards = day_entry.get("boards") or {}
            if not isinstance(boards, dict):
                continue
            for board_name, entries in boards.items():
                if board_name == "two_board" or not isinstance(entries, list):
                    continue
                for entry in entries:
                    if isinstance(entry, dict):
                        stocks.append(
                            {
                                "code": str(entry.get("ticker") or "").strip(),
                                "name": str(entry.get("name") or "").strip(),
                                "board_count": _safe_int(entry.get("board_num")),
                            }
                        )
            break
        return [item for item in stocks if item["code"] and item["board_count"] >= 2]


def _normalize_limit_up_item(item: dict[str, Any]) -> dict[str, Any]:
    """fuyao涨停池 → MarketLimitHistoryItem 字段。"""
    return {
        "code": str(item.get("ticker") or "").strip(),
        "name": str(item.get("name") or "").strip(),
        "limit_time": _normalize_time(item.get("limit_up_time")),
        "seal_amount": _thousand_yuan_to_yuan(item.get("seal_money")),
        "seal_money": _thousand_yuan_to_yuan(item.get("seal_money")),
        "limit_tag": str(item.get("continue_day_text") or ""),
        "limit_count": _safe_int(item.get("continue_day_cnt")),
        "reason": str(item.get("limit_up_reason") or ""),
        "themes": "ST" if item.get("is_st") else ("新股" if item.get("is_new") else ""),
        "price": _safe_float(item.get("last_price")),
        "change_pct": _safe_float(item.get("price_change_ratio_pct")),
    }


def _normalize_limit_down_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": str(item.get("ticker") or "").strip(),
        "name": str(item.get("name") or "").strip(),
        "limit_time": _normalize_time(item.get("last_limit_time")),
        "open_time": _normalize_time(item.get("first_limit_time")),
        "price": _safe_float(item.get("last_price")),
        "change_pct": _safe_float(item.get("price_change_ratio_pct")),
        "turnover_rate": _safe_float(item.get("turnover_ratio_pct")),
    }


def _normalize_limit_break_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": str(item.get("ticker") or "").strip(),
        "name": str(item.get("name") or "").strip(),
        "open_times": _safe_int(item.get("open_times")),
        "price": _safe_float(item.get("last_price")),
        "change_pct": _safe_float(item.get("price_change_ratio_pct")),
        "turnover_rate": _safe_float(item.get("turnover_ratio_pct")),
        "turnover": _thousand_yuan_to_yuan(item.get("turnover")),
    }


def _normalize_quote_snapshot_item(item: dict[str, Any], snapshot_timestamp_ms: int) -> dict[str, Any]:
    """fuyao 行情快照 → 项目统一 quote 结构（与 tdxhub 对齐）。

    涨跌幅/振幅优先用上游值，缺失时由现价与昨收推算。
    """
    code = str(item.get("ticker") or "").strip()
    price = _safe_float(item.get("last_price"))
    prev_close = _safe_float(item.get("prev_price"))
    high = _safe_float(item.get("high_price"))
    low = _safe_float(item.get("low_price"))
    change_pct = _safe_float(item.get("price_change_ratio_pct"))
    if change_pct is None and price is not None and prev_close not in (None, 0):
        change_pct = (price - prev_close) / prev_close * 100
    amplitude = (
        (high - low) / prev_close * 100
        if high is not None and low is not None and prev_close not in (None, 0)
        else None
    )
    return {
        "code": code,
        "price": price,
        "last_close": prev_close,
        "open": _safe_float(item.get("open_price")),
        "high": high,
        "low": low,
        "change_amt": _safe_float(item.get("price_change")),
        "change_pct": change_pct,
        "amplitude_pct": amplitude,
        "volume": _safe_float(item.get("volume")),
        "amount": _safe_float(item.get("turnover")),
        # 快照接口只给批次级时间戳，按上海时区格式化为不带时区的 ISO 字符串
        "quoted_at": _snapshot_quoted_at(snapshot_timestamp_ms),
        "name": "",
    }


def _snapshot_quoted_at(timestamp_ms: int) -> str:
    """批次时间戳缺失时退回抓取时刻，保证 quoted_at 始终可用。"""
    if timestamp_ms <= 0:
        return datetime.now(_SHANGHAI_TIMEZONE).isoformat(timespec="seconds")
    return datetime.fromtimestamp(timestamp_ms / 1000, _SHANGHAI_TIMEZONE).isoformat(timespec="seconds")


def _normalize_valuation_item(item: dict[str, Any]) -> dict[str, Any]:
    """fuyao 估值快照 → 内部字段；上游空值保持 None，不补零。"""
    return {
        "code": str(item.get("ticker") or "").strip(),
        "thscode": str(item.get("thscode") or "").strip(),
        "name": (str(item.get("name")).strip() if item.get("name") else ""),
        "pe_ttm": _safe_float(item.get("pe_ttm")),
        "pe_mrq": _safe_float(item.get("pe_mrq")),
        "pb": _safe_float(item.get("pb_mrq")),
        "ps_ttm": _safe_float(item.get("ps_ttm")),
        "pcf_ttm": _safe_float(item.get("pcf_ttm")),
    }


def _normalize_ladder_item(item: dict[str, Any]) -> dict[str, Any]:
    """fuyao涨停池 → MarketLimitUpLadderStock 字段；涨停原因映射为板块名。"""
    limit_up_time = _normalize_time(item.get("limit_up_time"))
    return {
        "code": str(item.get("ticker") or "").strip(),
        "name": str(item.get("name") or "").strip(),
        "board_count": _safe_int(item.get("continue_day_cnt")),
        "limit_up_time": limit_up_time,
        "sector_code": "",
        "sector_name": str(item.get("limit_up_reason") or ""),
        # 09:25 集合竞价即封板即一字板
        "one_word": limit_up_time.startswith("09:25"),
        "amount": _thousand_yuan_to_yuan(item.get("seal_money")),
    }


fuyao_provider = FuyaoDataProvider()
