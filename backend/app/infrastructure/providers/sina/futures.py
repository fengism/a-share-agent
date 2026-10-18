"""新浪期货报价和历史行情适配器。"""

import json
import math
from typing import Any

import httpx

_HEADERS = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}


async def _get_text(url: str, client: httpx.AsyncClient | None = None, *, timeout: float = 8.0) -> str:
    if client is None:
        async with httpx.AsyncClient(timeout=timeout, headers=_HEADERS) as owned:
            return await _get_text(url, owned, timeout=timeout)
    # timeout 必须显式传下去：外部传入的 client 可能没有设置默认超时，
    # 漏传会让这个协程无期限挂住，拖死整条 asyncio.gather。
    try:
        response = await client.get(url, headers=_HEADERS, timeout=timeout)
    except TypeError:
        # 兼容不接受 timeout 关键字的自定义 client / 测试替身
        response = await client.get(url, headers=_HEADERS)
    response.raise_for_status()
    return str(response.content.decode("gbk", errors="ignore"))


def parse_domestic_quote(line: str) -> tuple[str, dict[str, Any]] | None:
    """解析单条新浪 nf_ 合约行情行，返回 (sina_code, quote)。

    上游字段布局经 akshare futures_zh_spot 列映射与 2026-09 实测双重核对：
    2 开盘 / 3 最高 / 4 最低 / 5 昨收 / 6 买价 / 8 最新价 / 10 昨结算 /
    13 持仓量 / 14 成交量 / 17 行情日期。
    """
    if "=" not in line or '"' not in line:
        return None
    code_part = line.split("=")[0].split("_")[-1]
    fields = line.split('"')[1].split(",")
    if len(fields) < 18:
        return None
    try:
        open_price = float(fields[2])
        high_price = float(fields[3])
        low_price = float(fields[4])
        # 涨跌幅官方口径基于昨结算价，优先取 fields[10]；昨收(fields[5])仅兜底
        prev_settle = float(fields[10]) if float(fields[10]) > 0 else float(fields[5])
        current_price = float(fields[8]) if float(fields[8]) > 0 else float(fields[6])
        if current_price > 0 and prev_settle > 0:
            change = current_price - prev_settle
            change_pct = change / prev_settle * 100
        else:
            # 非交易时段最新价与买价可能均为 0，输出 None 而不是 0/-100%
            change = None
            change_pct = None
        open_interest = float(fields[13])
        volume = float(fields[14])
        quote_date = fields[17]
        if not all(
            math.isfinite(value)
            for value in (open_price, high_price, low_price, prev_settle, current_price, open_interest, volume)
        ):
            return None
    except (ValueError, IndexError, OverflowError):
        return None
    return f"nf_{code_part}", {
        "price": round(current_price, 2) if current_price > 0 else None,
        "prev_settle": round(prev_settle, 2) if prev_settle > 0 else None,
        "change": round(change, 2) if change is not None else None,
        "change_pct": round(change_pct, 2) if change_pct is not None else None,
        "open": round(open_price, 2),
        "high": round(high_price, 2),
        "low": round(low_price, 2),
        "volume": int(volume),
        "open_interest": int(open_interest),
        "date": quote_date,
    }


def parse_futures_jsonp(text: str) -> list[dict[str, Any]]:
    """解析新浪行情接口返回的 JSONP 数组内容。"""
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        try:
            rows = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("新浪期货历史返回格式无效") from exc
        if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
            return rows
    raise ValueError("新浪期货历史返回格式无效")


def _number(value: str) -> float | None:
    try:
        parsed = float(value)
        return round(parsed, 4) if math.isfinite(parsed) else None
    except (ValueError, TypeError):
        return None


def parse_global_quote(line: str) -> tuple[str, dict[str, Any]] | None:
    if "=" not in line or '"' not in line:
        return None
    symbol, raw = line.split("=", 1)
    fields = raw.strip('"; \r\n').split(",")
    if len(fields) < 14:
        return None
    price, prev_settle, change = _number(fields[0]), _number(fields[7]), _number(fields[1])
    if change is None and price is not None and prev_settle is not None:
        change = round(price - prev_settle, 3)
    return symbol.removeprefix("var hq_str_").strip(), {
        "price": price,
        "prev_settle": prev_settle,
        "change": change,
        "change_pct": round(change / prev_settle * 100, 2) if change is not None and prev_settle else None,
        "date": fields[12],
    }


async def fetch_futures_quotes(symbols: list[str], *, client: httpx.AsyncClient | None = None):
    if not symbols:
        return {}
    text = await _get_text(f"https://hq.sinajs.cn/list={','.join(symbols)}", client, timeout=6.0)
    quotes = {}
    for line in text.strip().splitlines():
        parsed = parse_global_quote(line) if "hq_str_hf_" in line else parse_domestic_quote(line)
        if parsed is not None:
            quotes[parsed[0]] = parsed[1]
    return quotes


async def fetch_futures_history(symbol: str, *, client: httpx.AsyncClient | None = None):
    if symbol not in {"SC0", "CL", "OIL"}:
        raise ValueError(f"unsupported futures history: {symbol}")
    method = (
        "InnerFuturesNewService.getDailyKLine" if symbol == "SC0" else "GlobalFuturesService.getGlobalFuturesDailyKLine"
    )
    text = await _get_text(
        f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_{symbol}=/{method}?symbol={symbol}",
        client,
    )
    return parse_futures_jsonp(text)


def parse_crude_quote(line: str) -> tuple[str, dict[str, Any]] | None:
    if "hq_str_hf_" in line:
        return parse_global_quote(line)
    if "hq_str_nf_SC0" not in line or '"' not in line:
        return None
    fields = line.split('"')[1].split(",")
    if len(fields) < 18:
        return None
    # 原油看板沿用最新价/昨结算原值，不使用商品看板的买价兜底和两位小数口径。
    price, prev_settle = _number(fields[8]), _number(fields[10])
    change = round(price - prev_settle, 3) if price is not None and prev_settle is not None else None
    return "nf_SC0", {
        "price": price,
        "change": change,
        "change_pct": round(change / prev_settle * 100, 2) if change is not None and prev_settle else None,
        "date": fields[17],
    }


async def fetch_crude_oil_quotes(*, client: httpx.AsyncClient | None = None) -> dict[str, dict[str, Any]]:
    text = await _get_text("https://hq.sinajs.cn/list=nf_SC0,hf_CL,hf_OIL", client)
    quotes = {}
    for line in text.strip().splitlines():
        parsed = parse_crude_quote(line)
        if parsed is not None:
            quotes[parsed[0]] = parsed[1]
    return quotes
