"""个股资金流向服务。

通过东方财富接口获取个股各级资金流向数据（主力、超大单、大单、中单、小单）。
"""

import logging

from app.services.providers import get_provider

logger = logging.getLogger(__name__)


async def get_stock_fund_flow(code: str) -> list[dict]:
    """获取个股资金流向日级数据（最近 120 个交易日）。

    Param:
        code: 6 位股票代码
    Return:
        按日期倒序排列的资金流向列表，每条包含 date/main_net/small_net/mid_net/large_net/super_net
    """
    provider = get_provider("eastmoney")
    if not provider:
        logger.warning("东方财富数据源未就绪")
        return []
    rows = await provider.fetch_stock_fund_flow(code)
    return rows
