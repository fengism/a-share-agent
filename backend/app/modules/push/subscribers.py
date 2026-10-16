"""推送模块领域事件订阅者（Event Subscribers）。

自动监听系统核心领域事件，彻底解耦业务模块与推送渠道：
- daily_review.completed: 每日复盘生成并入库完成后触发
- potential_stocks.mined: 潜力股/题材挖掘完成后触发
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.events import event_bus
from app.modules.daily_review.models import DailyReviewResult
from app.modules.potential.schemas import PotentialDailyResult
from app.modules.push.dispatcher import dispatch_notification
from app.modules.push.formatters.daily_review import daily_review_formatter
from app.modules.push.formatters.potential_stocks import potential_stocks_formatter

logger = logging.getLogger(__name__)


async def on_daily_review_completed(review: DailyReviewResult | Any) -> None:
    """监听每日复盘完成事件并自动分发多通道推送。"""
    try:
        if not isinstance(review, DailyReviewResult):
            review = DailyReviewResult.model_validate(review)
        message = daily_review_formatter.format(review)
        results = await dispatch_notification(message)
        logger.info("每日复盘事件通知分发完成: date=%s results=%s", review.date, results)
    except Exception as exc:  # noqa: BLE001 - 异常不向外冒泡
        logger.warning("每日复盘通知分发失败: %s", exc, exc_info=True)


async def on_potential_stocks_mined(result: PotentialDailyResult | Any) -> None:
    """监听潜力股挖掘完成事件并自动分发多通道推送。"""
    try:
        if not isinstance(result, PotentialDailyResult):
            result = PotentialDailyResult.model_validate(result)
        message = potential_stocks_formatter.format(result)
        results = await dispatch_notification(message)
        logger.info("潜力股挖掘事件通知分发完成: date=%s results=%s", result.date, results)
    except Exception as exc:  # noqa: BLE001
        logger.warning("潜力股挖掘通知分发失败: %s", exc, exc_info=True)


_subscribers_registered = False


def register_push_subscribers() -> None:
    """注册推送事件监听器到全局事件总线。"""
    global _subscribers_registered
    if _subscribers_registered:
        return
    event_bus.subscribe("daily_review.completed", on_daily_review_completed)
    event_bus.subscribe(DailyReviewResult, on_daily_review_completed)
    event_bus.subscribe("potential_stocks.mined", on_potential_stocks_mined)
    event_bus.subscribe(PotentialDailyResult, on_potential_stocks_mined)
    _subscribers_registered = True
    logger.info("推送模块领域事件订阅者已注册就绪")
