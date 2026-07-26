"""估值模块 — 按领域拆分。"""

from app.services.stock.valuation.orchestrator import get_valuation
from app.services.stock.valuation.detail import get_valuation_detail

# 以下内部符号为测试和子模块访问而公开，对应旧版单文件 valuation.py 的顶层函数。
from app.services.stock.valuation.helpers import (
    _annualize_report_metric,
    _normalize_peg_growth_rate,
    _parse_forecast_year,
)
from app.services.stock.valuation.profile import _derive_peg_growth_rate
from app.services.stock.valuation.methods import _build_peg_valuation
from app.utils.cache import cache

__all__ = [
    "get_valuation", "get_valuation_detail",
    "_annualize_report_metric", "_normalize_peg_growth_rate", "_parse_forecast_year",
    "_derive_peg_growth_rate", "_build_peg_valuation",
    "cache",
]
