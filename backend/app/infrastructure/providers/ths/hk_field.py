"""同花顺港股行业对比（F10 行业地位与同业公司数据抓取）。

页面结构（以 https://basic.10jqka.com.cn/{ths_code}/field.html 为例）：
1. 行业分类：`p.threecate span` 包含三级行业路径及公司总数，例如：
   「资讯科技业 - 软件服务 - 游戏软件（共24家）」
2. 图表与对比数据：`<div id="fieldsChartData" style="display:none">` 包含 JSON 格式的按报告期聚合的多公司指标行：
   格式为 `{"2026中报": [[代码, 简称, 总股本, 资产总计, 市盈率, 市净率, 流动资产, 负债合计, 资产负债率, 税后利润], ...], "2025年报": [...]}`
   其中市盈率可能为 "亏损"，需标记并转为 None。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.market import safe_float
from app.infrastructure.providers.ths.hk_f10 import fetch_ths_f10_page, ths_f10_code_segment
from app.infrastructure.providers.ths.transport import ThsTransport

logger = logging.getLogger(__name__)

_THREE_CATE_PATTERN = re.compile(r"^(.*?)(?:（共\s*(\d+)\s*家）|\(共\s*(\d+)\s*家\))")


def _normalize_hk_peer_code(raw_code: str) -> str:
    digits = "".join(ch for ch in str(raw_code or "") if ch.isdigit())
    return digits.zfill(5)


def _parse_row(row: list[Any]) -> dict[str, Any]:
    if len(row) < 10:
        return {}
    code = _normalize_hk_peer_code(str(row[0]))
    name = str(row[1]).strip()
    total_shares = safe_float(row[2])
    total_assets = safe_float(row[3])

    pe_raw = str(row[4]).strip()
    is_pe_loss = "亏损" in pe_raw
    pe = None if is_pe_loss else safe_float(pe_raw)

    pb = safe_float(row[5])
    current_assets = safe_float(row[6])
    total_liabilities = safe_float(row[7])
    debt_ratio = safe_float(row[8])
    if debt_ratio is not None:
        debt_ratio = round(debt_ratio, 2)
    net_profit = safe_float(row[9])

    return {
        "code": code,
        "name": name,
        "total_shares": total_shares,
        "total_assets": total_assets,
        "pe": pe,
        "is_pe_loss": is_pe_loss,
        "pb": pb,
        "current_assets": current_assets,
        "total_liabilities": total_liabilities,
        "debt_to_assets_ratio": debt_ratio,
        "net_profit": net_profit,
    }


def fetch_hk_industry_comparison(
    transport: ThsTransport,
    code: str,
) -> dict[str, Any]:
    """抓取并解析同花顺港股 F10 行业对比数据。"""
    soup = fetch_ths_f10_page(transport, code, "field.html")

    threecate = soup.select_one("p.threecate span")
    cat_text = threecate.get_text().strip() if threecate else ""

    m = _THREE_CATE_PATTERN.search(cat_text)
    if m:
        industry_path = m.group(1).strip()
        count_str = m.group(2) or m.group(3)
        company_count = int(count_str) if count_str else 0
    else:
        industry_path = cat_text
        company_count = 0

    parts = [p.strip() for p in industry_path.split("-") if p.strip()]
    industry = parts[0] if parts else ""
    sub_industry = parts[1] if len(parts) > 1 else ""
    segment = parts[2] if len(parts) > 2 else ""

    chart_div = soup.find("div", id="fieldsChartData")
    period_data: dict[str, list[dict[str, Any]]] = {}
    periods: list[str] = []

    if chart_div and chart_div.text.strip():
        try:
            raw_data = json.loads(chart_div.text.strip())
            if isinstance(raw_data, dict):
                periods = list(raw_data.keys())
                for period_name, rows in raw_data.items():
                    parsed_rows = []
                    if isinstance(rows, list):
                        for row in rows:
                            if isinstance(row, list):
                                item = _parse_row(row)
                                if item:
                                    parsed_rows.append(item)
                    period_data[period_name] = parsed_rows
        except Exception as exc:
            logger.warning("解析港股 %s fieldsChartData 失败: %s", code, exc)

    return {
        "code": _normalize_hk_peer_code(code),
        "industry": industry,
        "sub_industry": sub_industry,
        "segment": segment,
        "industry_path": industry_path,
        "company_count": company_count or (len(period_data[periods[0]]) if periods else 0),
        "periods": periods,
        "period_data": period_data,
        "source": "ths",
        "source_url": f"https://basic.10jqka.com.cn/{ths_f10_code_segment(code)}/field.html",
    }
