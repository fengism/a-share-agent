"""个股技术指标聚合服务。"""

import logging

from app.financial_data.stock.quotes.kline import get_kline
from app.financial_data.stock.quotes.technical import calculate_all
from app.financial_data.stock.quotes.technical_schemas import TechnicalIndicators

logger = logging.getLogger(__name__)


async def get_technical_indicators(code: str) -> TechnicalIndicators:
    """加载日 K 线并计算常用技术指标。"""
    kline = await get_kline(code)
    indicators = TechnicalIndicators.model_validate(calculate_all(kline.items))
    logger.info("技术指标计算完成: code=%s, 数据点=%d", code, len(kline.items))
    return indicators
