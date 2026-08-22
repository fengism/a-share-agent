"""声明式量化策略协议、加载、编译与执行。"""

from app.modules.quant.strategies.contracts import StrategySnapshot
from app.modules.quant.strategies.registry import get_strategy_registry

__all__ = ["StrategySnapshot", "get_strategy_registry"]

