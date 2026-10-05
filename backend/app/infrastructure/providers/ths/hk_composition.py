"""同花顺港股主营构成分析抓取能力。

港股与 A 股在这里是反的：A 股 ``operate.html`` 的「主营构成分析」面板是
``加载中...``（JS 异步拉取，静态 HTML 里没有数据），所以项目里 A 股主营构成走
新浪 ``getGrossRevenue``；而港股同一页面把构成表**服务端直出**，可以直接解析。

已核验的页面结构（8 只港股样本，结构一致）：

* 页面固定有 3 个 ``table.m_table.m_hl.company``，分别对应 3 个报告期；当期那张
  的 class 不含 ``none``，历史期含 ``none``。静态 HTML 不暴露报告期本身。
* 维度行以「按」开头（``按业务分`` / ``按地区分``）且带 rowspan 覆盖整段；
  港股没有「按产品分」。
* 数据行为 ``[名称, '', 占比]``；名称带括号的（如 ``(个人银行业务)``）是上一行的
  细分项。
* 合计行（``营业额`` / ``合计``）不是构成项，需剔除。
* 金额列在静态 HTML 里没有，只有占比，因此金额一律留空，不做任何推算。
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from app.core.market import is_hk_code
from app.infrastructure.providers.ths.hk_f10 import fetch_ths_f10_page, ths_f10_code_segment
from app.infrastructure.providers.ths.transport import ThsTransport

# 港股同花顺只提供按业务/按地区两个维度，没有按产品分
_DIMENSION_BY_PREFIX = {
    "按业务分": "by_business",
    "按地区分": "by_region",
}
# 合计行不是构成项
_TOTAL_LABELS = frozenset({"营业额", "合计", "总计", "总收入"})
_SUB_ITEM_PATTERN = re.compile(r"^[（(](.+)[）)]$")
_MAX_SHARE_PCT = 100.0


def _parse_share_pct(text: str) -> float | None:
    """解析占比；同花顺把数值写成 ``48.06`` 或 ``-0.03``。"""
    cleaned = text.strip().replace("%", "").replace(",", "")
    if not cleaned:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    # 占比不可能超过 100（个位数小数点漂移也远小于此），越界说明列被误读
    if not -_MAX_SHARE_PCT <= value <= _MAX_SHARE_PCT:
        return None
    return value


def _current_period_table(soup: BeautifulSoup) -> BeautifulSoup | None:
    """当期报告期的构成表：class 含 company 且不含 none。"""
    tables = [
        table
        for table in soup.find_all("table")
        if "company" in (table.get("class") or [])
    ]
    if not tables:
        return None
    for table in tables:
        if "none" not in (table.get("class") or []):
            return table
    return tables[0]


def _row_cells(row) -> list[str]:
    return [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]


def _last_share(cells: list[str]) -> float | None:
    """取该行最后一个能解析成占比的 cell；合并单元格会让有效值不在固定列位。"""
    for cell in reversed(cells):
        share = _parse_share_pct(cell)
        if share is not None:
            return share
    return None


def _append_item(
    result: dict[str, list[dict[str, Any]]],
    dimension: str,
    name: str,
    share_pct: float,
) -> None:
    if not name or name in _TOTAL_LABELS:
        return
    sub_match = _SUB_ITEM_PATTERN.match(name)
    result[dimension].append({
        "class_name": sub_match.group(1).strip() if sub_match else name,
        "is_sub_item": sub_match is not None,
        # 同花顺静态页面只给占比；金额缺失就留空，不按占比反推
        "revenue_share_pct": share_pct,
    })


def parse_hk_revenue_composition(table) -> dict[str, list[dict[str, Any]]]:
    """把一张构成表解析成 ``{维度: [构成项]}``。

    行形态有三种，靠「末列能否解析成占比」区分：

    * 维度列表头：``['按业务分', '项目名称', '营业收入 (人民币元)', '占比 (%)']``
    * 维度行兼首个构成项：``['按地区分', '中国', '', '88.08']``（地区段首行）
    * 普通数据行：``['<名称>', '', '<占比>']``
    """
    result: dict[str, list[dict[str, Any]]] = {}
    dimension: str | None = None
    for row in table.find_all("tr"):
        cells = _row_cells(row)
        if not cells:
            continue
        head = cells[0].strip()
        if head in _DIMENSION_BY_PREFIX:
            dimension = _DIMENSION_BY_PREFIX[head]
            result.setdefault(dimension, [])
            inline_share = _last_share(cells[1:])
            if inline_share is None or len(cells) < 2:
                continue
            _append_item(result, dimension, cells[1].strip(), inline_share)
            continue
        if dimension is None:
            continue
        share_pct = _last_share(cells[1:])
        if share_pct is None:
            continue
        _append_item(result, dimension, head, share_pct)
    return result


def fetch_hk_revenue_breakdown(transport: ThsTransport, code: str) -> dict[str, Any]:
    """抓取港股最新披露的主营构成（仅占比）。"""
    if not is_hk_code(code):
        raise ValueError(f"同花顺主营构成仅支持港股代码: {code}")
    soup = fetch_ths_f10_page(transport, code, "operate.html")
    table = _current_period_table(soup)
    dimensions = parse_hk_revenue_composition(table) if table is not None else {}
    return {
        "code": code,
        "symbol": ths_f10_code_segment(code),
        "source": "ths",
        # 表头金额单位随公司报表币种而定（人民币元/港元都有），且金额列本身不在
        # 静态页面里，因此这里不声称任何币种，避免把港币当成人民币。
        "amount_unit": None,
        "amount_unit_inferred": False,
        "by_business": dimensions.get("by_business", []),
        "by_region": dimensions.get("by_region", []),
    }


__all__ = ["fetch_hk_revenue_breakdown", "parse_hk_revenue_composition"]
