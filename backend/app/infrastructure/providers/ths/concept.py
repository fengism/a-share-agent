"""同花顺概念抓取能力。"""

from __future__ import annotations

import logging

from app.infrastructure.providers.ths.hk_f10 import fetch_ths_f10_page
from app.infrastructure.providers.ths.transport import ThsTransport

logger = logging.getLogger(__name__)


def fetch_stock_concepts(
    transport: ThsTransport,
    code: str,
) -> list[str]:
    """从同花顺 concept.html 抓取个股官方所属概念列表。

    Param:
        transport: 同花顺 HTTP 传输
        code: 股票代码（纯数字或标准代码）
    Return:
        概念名称列表（去重、保序）
    """
    code_raw = code.split(".")[0]
    try:
        soup = fetch_ths_f10_page(transport, code_raw, "concept.html")
        cells = soup.select("td.gnName")
        concepts: list[str] = []
        for cell in cells:
            name = "".join(cell.get_text().split()).strip()
            if name and name not in concepts:
                concepts.append(name)
        return concepts
    except Exception as exc:
        logger.warning("抓取同花顺概念失败 code=%s: %s", code_raw, exc)
        return []


__all__ = ["fetch_stock_concepts"]
