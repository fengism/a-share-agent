"""全球宏观利率、国债收益率与美元外汇流动性服务。"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import akshare as ak
import httpx

from app.core.cache import market_cache as cache

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300

# push2 主域名有 IP 级风控（异常断连），回退到延时行情域名；
# 汇率场景缓存 300s，延时数据无感知差异。
_FX_HOSTS = (
    "https://push2.eastmoney.com",
    "https://push2delay.eastmoney.com",
)

# 上游 f12 返回代码 -> (result key, 展示名, 标准代码)。
# secid 经实测核对：离岸为 133.USDCNH，在岸为 120.USDCNYC（中间价口径，
# 返回代码 USDCNYC）；119 市场下不存在 USDCNH/USDCNY，请求会被静默忽略。
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
    params = {
        "fltt": "2",
        "invt": "2",
        "fields": "f12,f14,f2,f3,f4",
        "secids": "100.UDI,133.USDCNH,120.USDCNYC",
    }
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

    result = _default_fx_result()
    for host in _FX_HOSTS:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{host}/api/qt/ulist.np/get", params=params, headers=headers)
            _apply_fx_rows(result, resp.json().get("data", {}).get("diff", []))
        except Exception as exc:
            logger.warning("美元指数与外汇行情获取失败: host=%s, error=%s", host, exc)
            continue
        if result["usd_cny"]["value"] is not None:
            break

    return result


async def fetch_us_cn_treasury_yield_history(page_size: int = 300, page_number: int = 1) -> dict[str, Any]:
    """从东方财富数据中心获取中美国债收益率历史曲线、利差与期限结构。
    
    接口参考: https://data.eastmoney.com/cjsj/zmgzsyl.html
    数据源: RPTA_WEB_TREASURYYIELD
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPTA_WEB_TREASURYYIELD",
        "columns": "ALL",
        "sortColumns": "SOLAR_DATE",
        "sortTypes": "-1",
        "token": "894050c76af8597a853f5b408b759f5d",
        "pageNumber": str(page_number),
        "pageSize": str(page_size),
    }
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            json_data = resp.json()
            raw_data = json_data.get("result", {}).get("data", [])
            total_count = json_data.get("result", {}).get("count", 0)

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

                history.append({
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
                })

            latest = history[0] if history else {}
            cn_10y_val = latest.get("cn_10y")
            us_10y_val = latest.get("us_10y")
            spread_10y_val = latest.get("spread_10y")
            us_10y_2y_val = latest.get("us_10y_2y")

            spread_status = (
                "正常正利差"
                if (spread_10y_val is not None and spread_10y_val >= 0)
                else "中美利差倒挂（美债收益率高于中债）"
            )
            us_curve_status = (
                "收益率曲线平坦/倒挂"
                if (us_10y_2y_val is not None and us_10y_2y_val <= 0)
                else "收益率曲线正常陡峭"
            )

            # 期限结构对比 (Term Structure)
            term_structure = [
                {
                    "tenor": "2Y",
                    "cn_yield": latest.get("cn_2y"),
                    "us_yield": latest.get("us_2y"),
                    "spread": latest.get("spread_2y"),
                },
                {
                    "tenor": "5Y",
                    "cn_yield": latest.get("cn_5y"),
                    "us_yield": latest.get("us_5y"),
                    "spread": round(latest["cn_5y"] - latest["us_5y"], 4) if (latest.get("cn_5y") and latest.get("us_5y")) else None,
                },
                {
                    "tenor": "10Y",
                    "cn_yield": cn_10y_val,
                    "us_yield": us_10y_val,
                    "spread": spread_10y_val,
                },
                {
                    "tenor": "30Y",
                    "cn_yield": latest.get("cn_30y"),
                    "us_yield": latest.get("us_30y"),
                    "spread": round(latest["cn_30y"] - latest["us_30y"], 4) if (latest.get("cn_30y") and latest.get("us_30y")) else None,
                },
            ]

            return {
                "history": history,
                "term_structure": term_structure,
                "total_count": total_count,
                "latest": {
                    "date": latest.get("date", ""),
                    "china_10y_yield": cn_10y_val,
                    "china_2y_yield": latest.get("cn_2y"),
                    "china_5y_yield": latest.get("cn_5y"),
                    "china_30y_yield": latest.get("cn_30y"),
                    "china_10y_2y_spread": latest.get("cn_10y_2y"),
                    "us_10y_yield": us_10y_val,
                    "us_2y_yield": latest.get("us_2y"),
                    "us_5y_yield": latest.get("us_5y"),
                    "us_30y_yield": latest.get("us_30y"),
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
        df = await asyncio.to_thread(ak.bond_zh_us_rate)
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

            latest_row = history[-1] if history else {}
            cn_10y = latest_row.get("cn_10y")
            us_10y = latest_row.get("us_10y")
            spread_10y = latest_row.get("spread_10y")
            return {
                "history": list(reversed(history)),
                "term_structure": [
                    {"tenor": "2Y", "cn_yield": latest_row.get("cn_2y"), "us_yield": latest_row.get("us_2y"), "spread": None},
                    {"tenor": "10Y", "cn_yield": cn_10y, "us_yield": us_10y, "spread": spread_10y},
                ],
                "total_count": len(history),
                "latest": {
                    "date": latest_row.get("date", ""),
                    "china_10y_yield": cn_10y,
                    "china_2y_yield": latest_row.get("cn_2y"),
                    "us_10y_yield": us_10y,
                    "us_2y_yield": latest_row.get("us_2y"),
                    "us_china_10y_spread": spread_10y,
                    "us_china_spread_status": "正常正利差" if (spread_10y and spread_10y >= 0) else "中美利差倒挂",
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
    cache_key = f"treasury_yield_curve_{page_size}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = await fetch_us_cn_treasury_yield_history(page_size=page_size)
    cache.set(cache_key, data, ttl=_CACHE_TTL_SECONDS)
    return data


async def get_global_macro_rates() -> dict[str, Any]:
    """获取全球宏观基准利率、国债收益率与美元外汇流动性看板。"""
    cache_key = "global_macro_rates_summary_v2"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    fx_data, bond_bundle = await asyncio.gather(
        fetch_fx_and_dollar_index(),
        fetch_us_cn_treasury_yield_history(page_size=300),
        return_exceptions=True,
    )

    if isinstance(fx_data, Exception):
        fx_data = {}
    if isinstance(bond_bundle, Exception):
        bond_bundle = {"history": [], "term_structure": [], "latest": {}, "total_count": 0}

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
        "central_bank_policy_rates": {
            "china_lpr_1y": "3.10% (中国1年期贷款市场报价利率)",
            "china_lpr_5y": "3.60% (中国5年期以上LPR/房贷基准)",
            "us_fed_funds_rate": "4.25% - 4.50% (美联储联邦基金目标利率)",
        },
        "market_implications": {
            "us_10y_impact": "美债10年期收益率是全球资产定价之锚（折现率），高位压制科技成长股估值，回落有利于成长股估值修复。",
            "us_china_spread_impact": "中美10Y利差倒挂幅度收窄或转正时，有利于人民币汇率企稳及北向资金中长期配置型流入。",
            "dxy_cnh_impact": "美元指数回调、离岸人民币升值通常有利于 A 股核心资产和白马蓝筹行情。",
        },
    }

    cache.set(cache_key, response, ttl=_CACHE_TTL_SECONDS)
    return response
