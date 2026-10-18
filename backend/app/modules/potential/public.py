"""潜力股挖掘模块的稳定出口。"""

from app.modules.potential.performance import compute_potential_performance
from app.modules.potential.schemas import (
    PotentialDailyResult,
    PotentialDateItem,
    PotentialPerformanceItem,
    PotentialPerformanceSummary,
    PotentialRunStatus,
    PotentialStockItem,
)
from app.modules.potential.screening import select_candidates
from app.modules.potential.service import (
    get_potential_result,
    list_potential_date_items,
    mine_potential_stocks,
    mining_run_status,
    run_daily_mining,
    run_scheduled_daily_mining,
    start_daily_mining_background,
)

__all__ = [
    "PotentialDateItem",
    "PotentialDailyResult",
    "PotentialPerformanceItem",
    "PotentialPerformanceSummary",
    "PotentialRunStatus",
    "PotentialStockItem",
    "compute_potential_performance",
    "get_potential_result",
    "mining_run_status",
    "list_potential_date_items",
    "mine_potential_stocks",
    "run_daily_mining",
    "run_scheduled_daily_mining",
    "select_candidates",
    "start_daily_mining_background",
]
