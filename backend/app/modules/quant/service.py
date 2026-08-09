"""量化回测应用服务。"""

import asyncio
from typing import Any

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore, misc_semaphore
from app.core.market import normalize_code, normalize_index_code
from app.infrastructure.persistence import portfolio as portfolio_store
from app.market_data.market.public import get_index_kline
from app.market_data.stock.public import get_historical_bars, historical_bar_hash
from app.modules.quant.engine import run_backtest
from app.modules.quant.persistence import runs as run_store
from app.modules.quant.persistence import strategies as strategy_store
from app.modules.quant.schemas import (
    QuantBacktestCreate,
    QuantBacktestList,
    QuantBacktestRun,
    QuantSavedStrategy,
    QuantStrategyConfig,
    QuantStrategyPreset,
    QuantStrategySave,
)

MAX_ACTIVE_RUNS_PER_USER = 2


def strategy_presets() -> list[QuantStrategyPreset]:
    return [
        QuantStrategyPreset(
            key="ma_cross",
            name="双均线趋势",
            description="短期均线上穿长期均线后持有，跌破后退出。",
            config=QuantStrategyConfig(type="ma_cross", fast_period=5, slow_period=20),
        ),
        QuantStrategyPreset(
            key="momentum_breakout",
            name="动量突破",
            description="突破近 20 日高点后跟随趋势，跌破均值后退出。",
            config=QuantStrategyConfig(type="momentum_breakout", lookback_period=20),
        ),
        QuantStrategyPreset(
            key="rsi_reversion",
            name="RSI 均值回归",
            description="RSI 进入超卖区间后买入，进入超买区间后退出。",
            config=QuantStrategyConfig(type="rsi_reversion", rsi_period=14, buy_threshold=30, sell_threshold=70),
        ),
    ]


def _to_saved_strategy(row: strategy_store.SavedStrategyRow) -> QuantSavedStrategy:
    return QuantSavedStrategy(
        id=row.id,
        name=row.name,
        config=QuantStrategyConfig.model_validate(row.config),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def save_user_strategy(request: QuantStrategySave, user_id: int) -> QuantSavedStrategy:
    row = await call_blocking(
        strategy_store.save_strategy,
        user_id,
        request.name.strip(),
        request.config.model_dump(mode="json"),
        semaphore=database_semaphore,
    )
    return _to_saved_strategy(row)


async def list_user_strategies(user_id: int) -> list[QuantSavedStrategy]:
    rows = await call_blocking(strategy_store.list_strategies, user_id, semaphore=database_semaphore)
    return [_to_saved_strategy(row) for row in rows]


async def delete_user_strategy(strategy_id: int, user_id: int) -> bool:
    return await call_blocking(
        strategy_store.delete_strategy,
        user_id,
        strategy_id,
        semaphore=database_semaphore,
    )


def _to_api(row: run_store.QuantRunRow) -> QuantBacktestRun:
    return QuantBacktestRun(
        id=row.id,
        name=row.name,
        status=row.status,
        request=QuantBacktestCreate.model_validate(row.request),
        result=row.result,
        error=row.last_error,
        attempts=row.attempts,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


async def _resolve_request(request: QuantBacktestCreate, user_id: int) -> QuantBacktestCreate:
    payload = request.model_copy(deep=True)
    if payload.universe.source == "portfolio":
        rows = await call_blocking(
            portfolio_store.list_positions,
            user_id,
            semaphore=database_semaphore,
        )
        payload.universe.codes = list(dict.fromkeys(row["stock_code"] for row in rows))
    payload.universe.codes = [normalize_code(code).raw for code in payload.universe.codes]
    if not payload.universe.codes:
        raise ValueError("股票池不能为空")
    if len(payload.universe.codes) > 10:
        raise ValueError("股票池最多支持 10 只股票")
    payload.benchmark = normalize_index_code(payload.benchmark.strip().lower())
    if not payload.benchmark.isdigit() or len(payload.benchmark) != 6:
        raise ValueError("基准指数代码必须为 6 位数字")
    return payload


async def create_backtest(request: QuantBacktestCreate, user_id: int) -> QuantBacktestRun:
    resolved = await _resolve_request(request, user_id)
    row = await call_blocking(
        run_store.create_run,
        user_id,
        resolved.name,
        resolved.model_dump(mode="json"),
        max_active_runs=MAX_ACTIVE_RUNS_PER_USER,
        semaphore=database_semaphore,
    )
    return _to_api(row)


async def get_backtest(run_id: str, user_id: int) -> QuantBacktestRun | None:
    row = await call_blocking(run_store.get_run, user_id, run_id, semaphore=database_semaphore)
    return _to_api(row) if row else None


async def list_backtests(user_id: int, *, limit: int = 50) -> QuantBacktestList:
    rows = await call_blocking(run_store.list_runs, user_id, limit=limit, semaphore=database_semaphore)
    return QuantBacktestList(items=[_to_api(row) for row in rows])


async def execute_backtest(request: QuantBacktestCreate) -> tuple[dict[str, Any], dict[str, Any]]:
    bar_sets = await asyncio.gather(
        *(
            get_historical_bars(
                code,
                request.start_date,
                request.end_date,
                period="daily",
                adjust="qfq",
            )
            for code in request.universe.codes
        )
    )
    benchmark = await get_index_kline(
        request.benchmark,
        period="daily",
        start_date=request.start_date.isoformat(),
        end_date=request.end_date.isoformat(),
    )
    benchmark_hash = historical_bar_hash(request.benchmark, "daily", "", benchmark.items)
    result = await call_blocking(
        run_backtest,
        {bar_set.code: bar_set.items for bar_set in bar_sets},
        benchmark.items,
        request.strategy,
        request.execution,
        data_hashes=[*(bar_set.data_hash for bar_set in bar_sets), benchmark_hash],
        data_sources=[*(bar_set.source for bar_set in bar_sets), "benchmark-provider-chain"],
        semaphore=misc_semaphore,
    )
    input_snapshot = {
        "stocks": {
            bar_set.code: [item.model_dump(mode="json") for item in bar_set.items]
            for bar_set in bar_sets
        },
        "benchmark": [item.model_dump(mode="json") for item in benchmark.items],
    }
    return result.model_dump(mode="json"), input_snapshot


async def cancel_backtest(run_id: str, user_id: int) -> bool:
    return await call_blocking(run_store.cancel, user_id, run_id, semaphore=database_semaphore)


async def retry_backtest(run_id: str, user_id: int) -> bool:
    return await call_blocking(run_store.retry_failed, user_id, run_id, semaphore=database_semaphore)


async def delete_backtest(run_id: str, user_id: int) -> bool:
    return await call_blocking(run_store.delete_run, user_id, run_id, semaphore=database_semaphore)
