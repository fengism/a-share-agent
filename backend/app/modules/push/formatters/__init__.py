"""消息格式化器包。"""

from app.modules.push.formatters.base import NotificationFormatter
from app.modules.push.formatters.daily_review import (
    DailyReviewFormatter,
    daily_review_formatter,
    format_daily_review_feishu_card,
    format_daily_review_wecom_markdown,
)
from app.modules.push.formatters.potential_stocks import (
    PotentialStocksFormatter,
    format_potential_stocks_feishu_card,
    format_potential_stocks_wecom_markdown,
    potential_stocks_formatter,
)

__all__ = [
    "DailyReviewFormatter",
    "NotificationFormatter",
    "PotentialStocksFormatter",
    "daily_review_formatter",
    "format_daily_review_feishu_card",
    "format_daily_review_wecom_markdown",
    "format_potential_stocks_feishu_card",
    "format_potential_stocks_wecom_markdown",
    "potential_stocks_formatter",
]
