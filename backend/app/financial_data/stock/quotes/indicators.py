"""个股技术指标聚合服务。"""

import logging
import re

from app.financial_data.stock.quotes.kline import get_kline
from app.financial_data.stock.quotes.technical import calculate_all
from app.financial_data.stock.quotes.technical_schemas import TechnicalIndicators

logger = logging.getLogger(__name__)

_HK_CODE_PATTERN = re.compile(r"^(?:hk)?(\d{1,5})$", re.IGNORECASE)


async def get_technical_indicators(
    code: str,
    period: str = "daily",
    start_date: str = "",
    end_date: str = "",
) -> TechnicalIndicators:
    """加载指定周期与日期范围的 K 线并计算常用技术指标。"""
    raw_code = code.strip()
    if _HK_CODE_PATTERN.fullmatch(raw_code):
        from app.financial_data.hk.service import hk_market_service, normalize_hk_code

        hk_code = normalize_hk_code(raw_code)
        kline = await hk_market_service.get_stock_history(
            hk_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        kline = await get_kline(code, period=period, start_date=start_date, end_date=end_date)
    indicators = TechnicalIndicators.model_validate(calculate_all(kline.items))
    logger.info("技术指标计算完成: code=%s, 周期=%s, 数据点=%d", code, period, len(kline.items))
    return indicators
