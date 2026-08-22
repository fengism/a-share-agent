"""多股票指标对比业务的稳定入口。"""

from app.modules.stock_comparison.service import compare_stocks

__all__ = ["compare_stocks"]
