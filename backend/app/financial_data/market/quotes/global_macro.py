"""全球宏观利率、国债收益率与美元外汇流动性服务。"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import (
    akshare_semaphore,
    call_blocking,
    eastmoney_semaphore,
    nbs_semaphore,
)
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300
# 政策利率取不到时的显式占位。刻意不用写死的数值冒充实时数据。
_RATE_UNAVAILABLE = "暂不可用"

_FX_ROW_KEYS = {
    "UDI": ("dxy", "美元指数 (DXY)", "UDI"),
    "USDCNH": ("usd_cnh", "美元兑离岸人民币 (USD/CNH)", "USDCNH"),
    "USDCNYC": ("usd_cny", "美元兑在岸人民币 (USD/CNY)", "USDCNY"),
    "USDCNY": ("usd_cny", "美元兑在岸人民币 (USD/CNY)", "USDCNY"),
}


def _safe_float(val: Any) -> float | None:
    if val is None or val == "" or str(val).lower() == "nan" or str(val).lower() == "null":
        return None
    try:
        return round(float(val), 4)
    except (ValueError, TypeError):
        return None


def _default_fx_result() -> dict[str, Any]:
    return {
        "dxy": {"name": "美元指数 (DXY)", "code": "UDI", "value": None, "change": None, "change_pct": None},
        "usd_cnh": {"name": "美元兑离岸人民币 (USD/CNH)", "code": "USDCNH", "value": None, "change": None, "change_pct": None},
        "usd_cny": {"name": "美元兑在岸人民币 (USD/CNY)", "code": "USDCNY", "value": None, "change": None, "change_pct": None},
    }


def _apply_fx_rows(result: dict[str, Any], diff: list[dict[str, Any]]) -> None:
    """把 ulist 接口返回的 diff 行写入 result，未知代码静默跳过。"""
    for row in diff:
        key_info = _FX_ROW_KEYS.get(str(row.get("f12", "")).upper())
        if key_info is None:
            continue
        key, name, code = key_info
        result[key] = {
            "name": name,
            "code": code,
            "value": _safe_float(row.get("f2")),
            "change": _safe_float(row.get("f4")),
            "change_pct": _safe_float(row.get("f3")),
        }


async def fetch_fx_and_dollar_index() -> dict[str, Any]:
    """获取美元指数 (DXY)、离岸人民币 (USD/CNH) 和在岸人民币 (USD/CNY) 实时行情。"""
    result = _default_fx_result()
    for delayed in (False, True):
        try:
            rows = await provider_gateway.call_blocking(
                "eastmoney",
                "fetch_fx_quotes_delayed" if delayed else "fetch_fx_quotes",
                get_provider("eastmoney").fetch_fx_quotes,
                delayed=delayed,
                semaphore=eastmoney_semaphore,
                is_fallback_attempt=delayed,
            )
            _apply_fx_rows(result, rows)
        except Exception as exc:
            logger.warning("美元指数与外汇行情获取失败: delayed=%s, error=%s", delayed, exc)
            continue
        if result["usd_cny"]["value"] is not None:
            break

    return result


async def fetch_us_cn_treasury_yield_history(page_size: int = 300, page_number: int = 1) -> dict[str, Any]:
    """从东方财富数据中心获取中美国债收益率历史曲线、利差与期限结构。

    接口参考: https://data.eastmoney.com/cjsj/zmgzsyl.html
    数据源: RPTA_WEB_TREASURYYIELD
    """
    try:
        result = await provider_gateway.call_blocking(
            "eastmoney",
            "fetch_treasury_yield_history",
            get_provider("eastmoney").fetch_treasury_yield_history,
            page_size,
            page_number,
            semaphore=eastmoney_semaphore,
        )
        raw_data = result.get("data", [])
        total_count = result.get("count", 0)

        history: list[dict[str, Any]] = []
        for row in raw_data:
            date_str = str(row.get("SOLAR_DATE", ""))[:10]
            cn_2y = _safe_float(row.get("EMM00588704"))
            cn_5y = _safe_float(row.get("EMM00166462"))
            cn_10y = _safe_float(row.get("EMM00166466"))
            cn_30y = _safe_float(row.get("EMM00166469"))
            cn_10y_2y = _safe_float(row.get("EMM01276014"))
            cn_gdp_growth = _safe_float(row.get("EMM00000024"))

            us_2y = _safe_float(row.get("EMG00001306"))
            us_5y = _safe_float(row.get("EMG00001308"))
            us_10y = _safe_float(row.get("EMG00001310"))
            us_30y = _safe_float(row.get("EMG00001312"))
            us_10y_2y = _safe_float(row.get("EMG01339436"))
            us_gdp_growth = _safe_float(row.get("EMG00159635"))

            spread_10y = round(cn_10y - us_10y, 4) if (cn_10y is not None and us_10y is not None) else None
            spread_2y = round(cn_2y - us_2y, 4) if (cn_2y is not None and us_2y is not None) else None

            history.append(
                {
                    "date": date_str,
                    "cn_2y": cn_2y,
                    "cn_5y": cn_5y,
                    "cn_10y": cn_10y,
                    "cn_30y": cn_30y,
                    "cn_10y_2y": cn_10y_2y,
                    "cn_gdp_growth": cn_gdp_growth,
                    "us_2y": us_2y,
                    "us_5y": us_5y,
                    "us_10y": us_10y,
                    "us_30y": us_30y,
                    "us_10y_2y": us_10y_2y,
                    "us_gdp_growth": us_gdp_growth,
                    "spread_10y": spread_10y,
                    "spread_2y": spread_2y,
                }
            )

        # 记录原始最新记录（用于追溯实际发布日期）
        latest_us_row = next((r for r in history if r.get("us_10y") is not None), {})
        latest_cn_row = next((r for r in history if r.get("cn_10y") is not None), {})

        # 沿时间正向（从旧到新，即列表逆向）进行前值填充 (LOCF)
        # 解决中美时区差（日间A股已收盘但美债未闭市）及各自法定节假日导致的缺值
        for i in range(len(history) - 2, -1, -1):
            curr = history[i]
            prev = history[i + 1]
            if curr.get("us_10y") is None and prev.get("us_10y") is not None:
                curr["us_10y"] = prev["us_10y"]
            if curr.get("us_2y") is None and prev.get("us_2y") is not None:
                curr["us_2y"] = prev["us_2y"]
            if curr.get("us_5y") is None and prev.get("us_5y") is not None:
                curr["us_5y"] = prev["us_5y"]
            if curr.get("us_30y") is None and prev.get("us_30y") is not None:
                curr["us_30y"] = prev["us_30y"]
            if curr.get("us_10y_2y") is None and prev.get("us_10y_2y") is not None:
                curr["us_10y_2y"] = prev["us_10y_2y"]

            if curr.get("cn_10y") is None and prev.get("cn_10y") is not None:
                curr["cn_10y"] = prev["cn_10y"]
            if curr.get("cn_2y") is None and prev.get("cn_2y") is not None:
                curr["cn_2y"] = prev["cn_2y"]
            if curr.get("cn_5y") is None and prev.get("cn_5y") is not None:
                curr["cn_5y"] = prev["cn_5y"]
            if curr.get("cn_30y") is None and prev.get("cn_30y") is not None:
                curr["cn_30y"] = prev["cn_30y"]
            if curr.get("cn_10y_2y") is None and prev.get("cn_10y_2y") is not None:
                curr["cn_10y_2y"] = prev["cn_10y_2y"]

            if curr.get("spread_10y") is None and curr.get("cn_10y") is not None and curr.get("us_10y") is not None:
                curr["spread_10y"] = round(curr["cn_10y"] - curr["us_10y"], 4)
            if curr.get("spread_2y") is None and curr.get("cn_2y") is not None and curr.get("us_2y") is not None:
                curr["spread_2y"] = round(curr["cn_2y"] - curr["us_2y"], 4)

        latest = history[0] if history else {}
        cn_10y_val = latest.get("cn_10y") if latest.get("cn_10y") is not None else latest_cn_row.get("cn_10y")
        us_10y_val = latest.get("us_10y") if latest.get("us_10y") is not None else latest_us_row.get("us_10y")
        spread_10y_val = (
            latest.get("spread_10y")
            if latest.get("spread_10y") is not None
            else (round(cn_10y_val - us_10y_val, 4) if (cn_10y_val is not None and us_10y_val is not None) else None)
        )
        us_10y_2y_val = (
            latest.get("us_10y_2y") if latest.get("us_10y_2y") is not None else latest_us_row.get("us_10y_2y")
        )

        spread_status = (
            f"正常正利差（中债高出 {spread_10y_val:.2f}%）"
            if (spread_10y_val is not None and spread_10y_val >= 0)
            else f"中美利差倒挂（美债高出 {abs(spread_10y_val):.2f}%）"
            if spread_10y_val is not None
            else "中美利差倒挂（美债收益率高于中债）"
        )
        us_curve_status = (
            "收益率曲线平坦/倒挂" if (us_10y_2y_val is not None and us_10y_2y_val <= 0) else "收益率曲线正常陡峭"
        )

        cn_2y_val = latest.get("cn_2y") if latest.get("cn_2y") is not None else latest_cn_row.get("cn_2y")
        us_2y_val = latest.get("us_2y") if latest.get("us_2y") is not None else latest_us_row.get("us_2y")
        cn_5y_val = latest.get("cn_5y") if latest.get("cn_5y") is not None else latest_cn_row.get("cn_5y")
        us_5y_val = latest.get("us_5y") if latest.get("us_5y") is not None else latest_us_row.get("us_5y")
        cn_30y_val = latest.get("cn_30y") if latest.get("cn_30y") is not None else latest_cn_row.get("cn_30y")
        us_30y_val = latest.get("us_30y") if latest.get("us_30y") is not None else latest_us_row.get("us_30y")

        # 期限结构对比 (Term Structure)
        term_structure = [
            {
                "tenor": "2Y",
                "cn_yield": cn_2y_val,
                "us_yield": us_2y_val,
                "spread": round(cn_2y_val - us_2y_val, 4)
                if (cn_2y_val is not None and us_2y_val is not None)
                else None,
            },
            {
                "tenor": "5Y",
                "cn_yield": cn_5y_val,
                "us_yield": us_5y_val,
                "spread": round(cn_5y_val - us_5y_val, 4)
                if (cn_5y_val is not None and us_5y_val is not None)
                else None,
            },
            {
                "tenor": "10Y",
                "cn_yield": cn_10y_val,
                "us_yield": us_10y_val,
                "spread": spread_10y_val,
            },
            {
                "tenor": "30Y",
                "cn_yield": cn_30y_val,
                "us_yield": us_30y_val,
                "spread": round(cn_30y_val - us_30y_val, 4)
                if (cn_30y_val is not None and us_30y_val is not None)
                else None,
            },
        ]

        return {
            "history": history,
            "term_structure": term_structure,
            "total_count": total_count,
            "latest": {
                "date": latest.get("date", ""),
                "china_date": latest_cn_row.get("date", latest.get("date", "")),
                "us_date": latest_us_row.get("date", latest.get("date", "")),
                "china_10y_yield": cn_10y_val,
                "china_2y_yield": cn_2y_val,
                "china_5y_yield": cn_5y_val,
                "china_30y_yield": cn_30y_val,
                "china_10y_2y_spread": latest.get("cn_10y_2y"),
                "us_10y_yield": us_10y_val,
                "us_2y_yield": us_2y_val,
                "us_5y_yield": us_5y_val,
                "us_30y_yield": us_30y_val,
                "us_10y_2y_spread": us_10y_2y_val,
                "us_china_10y_spread": spread_10y_val,
                "us_china_spread_status": spread_status,
                "us_yield_curve_status": us_curve_status,
            },
        }
    except Exception as exc:
        logger.warning("东方财富中美国债数据获取失败: %s", exc)
        # Fallback to akshare if direct eastmoney call fails
        return await _fallback_fetch_bond_yields()


async def _fallback_fetch_bond_yields() -> dict[str, Any]:
    """兜底从 akshare 获取中美国债数据。"""
    try:
        df = await provider_gateway.call_blocking(
            "akshare",
            "fetch_bond_yields",
            get_provider("akshare").fetch_bond_yields,
            semaphore=akshare_semaphore,
            is_fallback_attempt=True,
        )
        if df is not None and not df.empty:
            history = []
            for _, row in df.tail(100).iterrows():
                cn_10y = _safe_float(row.get("中国国债收益率10年"))
                cn_2y = _safe_float(row.get("中国国债收益率2年"))
                us_10y = _safe_float(row.get("美国国债收益率10年"))
                us_2y = _safe_float(row.get("美国国债收益率2年"))
                history.append({
                    "date": str(row.get("日期", "")),
                    "cn_2y": cn_2y,
                    "cn_10y": cn_10y,
                    "us_2y": us_2y,
                    "us_10y": us_10y,
                    "spread_10y": round(cn_10y - us_10y, 4) if (cn_10y and us_10y) else None,
                })

            reversed_history = list(reversed(history))
            latest_us_row = next((r for r in reversed_history if r.get("us_10y") is not None), {})
            latest_cn_row = next((r for r in reversed_history if r.get("cn_10y") is not None), {})

            for i in range(len(reversed_history) - 2, -1, -1):
                curr = reversed_history[i]
                prev = reversed_history[i + 1]
                if curr.get("us_10y") is None and prev.get("us_10y") is not None:
                    curr["us_10y"] = prev["us_10y"]
                if curr.get("us_2y") is None and prev.get("us_2y") is not None:
                    curr["us_2y"] = prev["us_2y"]
                if curr.get("cn_10y") is None and prev.get("cn_10y") is not None:
                    curr["cn_10y"] = prev["cn_10y"]
                if curr.get("cn_2y") is None and prev.get("cn_2y") is not None:
                    curr["cn_2y"] = prev["cn_2y"]
                if curr.get("spread_10y") is None and curr.get("cn_10y") is not None and curr.get("us_10y") is not None:
                    curr["spread_10y"] = round(curr["cn_10y"] - curr["us_10y"], 4)

            latest_row = reversed_history[0] if reversed_history else {}
            cn_10y = latest_row.get("cn_10y") if latest_row.get("cn_10y") is not None else latest_cn_row.get("cn_10y")
            us_10y = latest_row.get("us_10y") if latest_row.get("us_10y") is not None else latest_us_row.get("us_10y")
            spread_10y = (
                latest_row.get("spread_10y")
                if latest_row.get("spread_10y") is not None
                else (round(cn_10y - us_10y, 4) if (cn_10y is not None and us_10y is not None) else None)
            )
            cn_2y = latest_row.get("cn_2y") if latest_row.get("cn_2y") is not None else latest_cn_row.get("cn_2y")
            us_2y = latest_row.get("us_2y") if latest_row.get("us_2y") is not None else latest_us_row.get("us_2y")
            spread_status = (
                f"正常正利差（中债高出 {spread_10y:.2f}%）"
                if (spread_10y is not None and spread_10y >= 0)
                else f"中美利差倒挂（美债高出 {abs(spread_10y):.2f}%）"
                if spread_10y is not None
                else "中美利差倒挂"
            )
            return {
                "history": reversed_history,
                "term_structure": [
                    {"tenor": "2Y", "cn_yield": cn_2y, "us_yield": us_2y, "spread": round(cn_2y - us_2y, 4) if (cn_2y is not None and us_2y is not None) else None},
                    {"tenor": "10Y", "cn_yield": cn_10y, "us_yield": us_10y, "spread": spread_10y},
                ],
                "total_count": len(reversed_history),
                "latest": {
                    "date": latest_row.get("date", ""),
                    "china_date": latest_cn_row.get("date", latest_row.get("date", "")),
                    "us_date": latest_us_row.get("date", latest_row.get("date", "")),
                    "china_10y_yield": cn_10y,
                    "china_2y_yield": cn_2y,
                    "us_10y_yield": us_10y,
                    "us_2y_yield": us_2y,
                    "us_china_10y_spread": spread_10y,
                    "us_china_spread_status": spread_status,
                    "us_yield_curve_status": "正常",
                },
            }
    except Exception as exc:
        logger.warning("akshare 兜底中美国债收益率获取失败: %s", exc)

    return {
        "history": [],
        "term_structure": [],
        "total_count": 0,
        "latest": {
            "date": "",
            "china_date": "",
            "us_date": "",
            "china_10y_yield": None,
            "china_2y_yield": None,
            "us_10y_yield": None,
            "us_2y_yield": None,
            "us_china_10y_spread": None,
            "us_china_spread_status": "暂无数据",
            "us_yield_curve_status": "暂无数据",
        },
    }


async def get_treasury_yield_curve(page_size: int = 300) -> dict[str, Any]:
    """获取中美国债收益率历史曲线、期限结构与利差。"""
    cache_key = f"treasury_yield_curve_v3_{page_size}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = await fetch_us_cn_treasury_yield_history(page_size=page_size)
    cache.set(cache_key, data, ttl=_CACHE_TTL_SECONDS)
    return data


async def fetch_crude_oil_data(client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    """获取原油主连实时快照与历史趋势数据。

    涵盖：
    - 国内：上海原油连续 (SC0，单位：元/桶)
    - 国际：NYMEX 纽约原油 (CL/WTI，单位：美元/桶)
    - 国际：ICE 布伦特原油 (OIL/Brent，单位：美元/桶)
    """
    provider = get_provider("sina")
    try:
        quote_map, sc_raw, cl_raw, oil_raw = await asyncio.gather(
            provider_gateway.call(
                "sina", "fetch_crude_oil_quotes", lambda: provider.fetch_crude_oil_quotes(client=client)
            ),
            provider_gateway.call(
                "sina", "fetch_futures_history_SC0", lambda: provider.fetch_futures_history("SC0", client=client)
            ),
            provider_gateway.call(
                "sina", "fetch_futures_history_CL", lambda: provider.fetch_futures_history("CL", client=client)
            ),
            provider_gateway.call(
                "sina", "fetch_futures_history_OIL", lambda: provider.fetch_futures_history("OIL", client=client)
            ),
            return_exceptions=True,
        )
        if isinstance(quote_map, Exception):
            quote_map = {}
        sc_raw = [] if isinstance(sc_raw, Exception) else sc_raw
        cl_raw = [] if isinstance(cl_raw, Exception) else cl_raw
        oil_raw = [] if isinstance(oil_raw, Exception) else oil_raw
        quotes = {}
        for key, code, symbol, name, unit in (
            ("sc0", "nf_SC0", "SC0", "上海原油连续", "元/桶"),
            ("wti", "hf_CL", "CL", "WTI纽约原油", "美元/桶"),
            ("brent", "hf_OIL", "OIL", "布伦特原油", "美元/桶"),
        ):
            quote = quote_map.get(code)
            quotes[key] = (
                None
                if quote is None
                else {
                    "symbol": symbol,
                    "name": name,
                    "unit": unit,
                    **{field: quote.get(field) for field in ("price", "change", "change_pct", "date")},
                }
            )

        sc_map = {item["d"]: _safe_float(item.get("c")) for item in sc_raw if "d" in item}
        cl_map = {item["date"]: _safe_float(item.get("close")) for item in cl_raw if "date" in item}
        oil_map = {item["date"]: _safe_float(item.get("close")) for item in oil_raw if "date" in item}

        # 统一日期维度：上海原油于 2018-03-26 上市，聚合 2018-03-26 之后的交易日
        all_dates = sorted(
            set(sc_map.keys())
            | {d for d in cl_map if d >= "2018-03-26"}
            | {d for d in oil_map if d >= "2018-03-26"}
        )

        history: list[dict[str, Any]] = []
        last_sc: float | None = None
        last_cl: float | None = None
        last_oil: float | None = None

        for d in all_dates:
            sc_val = sc_map.get(d)
            if sc_val is not None:
                last_sc = sc_val
            else:
                sc_val = last_sc

            cl_val = cl_map.get(d)
            if cl_val is not None:
                last_cl = cl_val
            else:
                cl_val = last_cl

            oil_val = oil_map.get(d)
            if oil_val is not None:
                last_oil = oil_val
            else:
                oil_val = last_oil

            history.append({
                "date": d,
                "sc_close": sc_val,
                "wti_close": cl_val,
                "brent_close": oil_val,
            })

        return {
            "sc0": quotes.get("sc0"),
            "wti": quotes.get("wti"),
            "brent": quotes.get("brent"),
            "history": history,
        }
    except Exception as exc:
        logger.warning("获取原油主连数据失败: %s", exc)
        return {
            "sc0": None,
            "wti": None,
            "brent": None,
            "history": [],
        }


async def get_crude_oil_data() -> dict[str, Any]:
    """获取原油主连数据（带缓存）。"""
    cache_key = "crude_oil_data_v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = await fetch_crude_oil_data()
    cache.set(cache_key, data, ttl=_CACHE_TTL_SECONDS)
    return data


async def fetch_policy_rates() -> dict[str, str]:
    """获取中美政策利率，全部来自实时数据源。

    此前这三个值是写死的字符串，会静默过期且没有任何来源标注——例如美联储目标区间
    长期停在 4.25%-4.50%，与实际值早已脱节。取不到时明确返回「暂不可用」，
    宁可让前端显示缺数据，也不输出一个看起来像实时数据的错数字。
    """
    result = {
        "china_lpr_1y": _RATE_UNAVAILABLE,
        "china_lpr_5y": _RATE_UNAVAILABLE,
        "us_fed_funds_rate": _RATE_UNAVAILABLE,
    }
    lpr_rows, fed_rows = await asyncio.gather(
        provider_gateway.call(
            "nbs",
            "fetch_china_lpr",
            lambda: call_blocking(get_provider("nbs").fetch_china_lpr, semaphore=nbs_semaphore),
            is_fallback_attempt=True,
        ),
        provider_gateway.call(
            "eastmoney",
            "fetch_us_fed_rate",
            lambda: call_blocking(
                get_provider("eastmoney").fetch_us_fed_rate, semaphore=eastmoney_semaphore
            ),
            is_fallback_attempt=True,
        ),
        return_exceptions=True,
    )
    if isinstance(lpr_rows, list) and lpr_rows:
        latest = lpr_rows[0]
        one_year = _safe_float(latest.get("LPR1Y"))
        five_year = _safe_float(latest.get("LPR5Y"))
        if one_year is not None:
            result["china_lpr_1y"] = f"{one_year:.2f}% (中国1年期贷款市场报价利率)"
        if five_year is not None:
            result["china_lpr_5y"] = f"{five_year:.2f}% (中国5年期以上LPR/房贷基准)"
    if isinstance(fed_rows, list) and fed_rows:
        # 东财该序列只给目标区间上限，因此只报上限，不臆造下限。
        upper = _safe_float(fed_rows[0].get("VALUE"))
        if upper is not None:
            result["us_fed_funds_rate"] = f"上限 {upper:.2f}% (美联储联邦基金目标利率)"
    unavailable = [key for key, value in result.items() if value == _RATE_UNAVAILABLE]
    if unavailable:
        logger.warning("政策利率数据源不可用: %s", ",".join(unavailable))
    return result


async def get_global_macro_rates() -> dict[str, Any]:
    """获取全球宏观基准利率、国债收益率与美元外汇流动性看板。"""
    cache_key = "global_macro_rates_summary_v4"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    fx_data, bond_bundle, crude_oil_bundle, policy_rates = await asyncio.gather(
        fetch_fx_and_dollar_index(),
        fetch_us_cn_treasury_yield_history(page_size=300),
        get_crude_oil_data(),
        fetch_policy_rates(),
        return_exceptions=True,
    )

    failed: list[str] = []
    if isinstance(fx_data, Exception):
        logger.warning("全球宏观外汇数据获取失败: %s", fx_data)
        failed.append("dollar_and_fx")
        fx_data = {}
    if isinstance(bond_bundle, Exception):
        logger.warning("全球宏观美债数据获取失败: %s", bond_bundle)
        failed.append("treasury_yields_and_spreads")
        bond_bundle = {"history": [], "term_structure": [], "latest": {}, "total_count": 0}
    if isinstance(crude_oil_bundle, Exception):
        logger.warning("全球宏观原油数据获取失败: %s", crude_oil_bundle)
        failed.append("crude_oil")
        crude_oil_bundle = {"sc0": None, "wti": None, "brent": None, "history": []}
    if isinstance(policy_rates, Exception):
        logger.warning("全球宏观政策利率获取失败: %s", policy_rates)
        policy_rates = {
            "china_lpr_1y": _RATE_UNAVAILABLE,
            "china_lpr_5y": _RATE_UNAVAILABLE,
            "us_fed_funds_rate": _RATE_UNAVAILABLE,
        }

    latest_bond = bond_bundle.get("latest", {})

    response = {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "dollar_and_fx": fx_data,
        "treasury_yields_and_spreads": latest_bond,
        "treasury_curve": {
            "history": bond_bundle.get("history", []),
            "term_structure": bond_bundle.get("term_structure", []),
            "total_count": bond_bundle.get("total_count", 0),
        },
        "central_bank_policy_rates": policy_rates,
        "market_implications": {
            "us_10y_impact": "美债10年期收益率是全球资产定价之锚（折现率），高位压制科技成长股估值，回落有利于成长股估值修复。",
            "us_china_spread_impact": "中美10Y利差倒挂幅度收窄或转正时，有利于人民币汇率企稳及北向资金中长期配置型流入。",
            "dxy_cnh_impact": "美元指数回调、离岸人民币升值通常有利于 A 股核心资产和白马蓝筹行情。",
        },
        "crude_oil": crude_oil_bundle,
    }

    # 上游整体故障时不要写缓存：否则一次抖动会把「数据源挂了」固化成 5 分钟的
    # 「今天没有数据」，且前端拿到的 JSON 结构完全合法，无法与真实空值区分。
    if failed:
        logger.warning("全球宏观看板存在失败分片，跳过缓存: %s", ",".join(failed))
        return response
    cache.set(cache_key, response, ttl=_CACHE_TTL_SECONDS)
    return response

