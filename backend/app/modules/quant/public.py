"""量化模块对 HTTP、Worker 和其他适配器开放的稳定入口。"""

from app.modules.quant.draft_service import (
    StrategyDraftConflictError,
    StrategyDraftGenerationError,
    StrategyDraftNotFoundError,
    backtest_strategy_draft,
    delete_strategy_draft,
    generate_strategy_draft,
    get_strategy_draft,
    list_strategy_drafts,
    publish_strategy_draft,
    update_strategy_draft,
    validate_strategy_draft,
)
from app.modules.quant.engine import build_target_positions
from app.modules.quant.job_processor import process_next_quant_job
from app.modules.quant.schemas import (
    QuantBacktestCreate,
    QuantBacktestList,
    QuantBacktestRun,
    QuantSavedStrategy,
    QuantStrategyDraft,
    QuantStrategyDraftBacktestRequest,
    QuantStrategyDraftGenerateRequest,
    QuantStrategyDraftPublishRequest,
    QuantStrategyDraftUpdateRequest,
    QuantStrategyPreset,
    QuantStrategyRegistryStatus,
    QuantStrategySave,
)
from app.modules.quant.service import (
    cancel_backtest,
    create_backtest,
    delete_backtest,
    delete_user_strategy,
    execute_backtest,
    get_backtest,
    list_backtests,
    list_user_strategies,
    retry_backtest,
    save_user_strategy,
    strategy_presets,
    strategy_registry_status,
)
from app.modules.quant.strategies.contracts import StrategySnapshot
from app.modules.quant.strategies.curation import (
    CURATED_STRATEGIES,
    CURATED_STRATEGY_KEYS,
    DEFAULT_MINING_WEIGHT,
    MINING_WEIGHTS,
    mining_weight,
)
from app.modules.quant.strategies.registry import configure_strategy_registry, get_strategy_registry
from app.modules.quant.strategies.watcher import StrategyDirectoryWatcher


async def run_strategy_reload_watcher(interval_seconds: float) -> None:
    await StrategyDirectoryWatcher(get_strategy_registry(), interval_seconds).run()

__all__ = [
    "CURATED_STRATEGIES",
    "CURATED_STRATEGY_KEYS",
    "DEFAULT_MINING_WEIGHT",
    "MINING_WEIGHTS",
    "QuantBacktestCreate",
    "QuantBacktestList",
    "QuantBacktestRun",
    "QuantSavedStrategy",
    "QuantStrategyDraft",
    "QuantStrategyDraftBacktestRequest",
    "QuantStrategyDraftGenerateRequest",
    "QuantStrategyDraftPublishRequest",
    "QuantStrategyDraftUpdateRequest",
    "QuantStrategyPreset",
    "QuantStrategyRegistryStatus",
    "QuantStrategySave",
    "StrategyDraftConflictError",
    "StrategyDraftGenerationError",
    "StrategyDraftNotFoundError",
    "StrategySnapshot",
    "backtest_strategy_draft",
    "build_target_positions",
    "cancel_backtest",
    "configure_strategy_registry",
    "create_backtest",
    "delete_backtest",
    "delete_strategy_draft",
    "delete_user_strategy",
    "execute_backtest",
    "generate_strategy_draft",
    "get_backtest",
    "get_strategy_draft",
    "get_strategy_registry",
    "list_backtests",
    "list_strategy_drafts",
    "list_user_strategies",
    "mining_weight",
    "process_next_quant_job",
    "publish_strategy_draft",
    "retry_backtest",
    "run_strategy_reload_watcher",
    "save_user_strategy",
    "strategy_presets",
    "strategy_registry_status",
    "update_strategy_draft",
    "validate_strategy_draft",
]
