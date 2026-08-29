"""量化回测应用服务。"""

import asyncio
from dataclasses import replace
from datetime import date, timedelta
from typing import Any

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore, misc_semaphore
from app.core.market import normalize_code, normalize_index_code
from app.financial_data.market.public import get_completed_market_date, get_index_kline
from app.financial_data.stock.public import HistoricalBarSet, get_historical_bars, historical_bar_hash
from app.modules.portfolio.public import list_held_stock_codes
from app.modules.quant.engine import run_backtest, strategy_warmup_bars
from app.modules.quant.persistence import runs as run_store
from app.modules.quant.persistence import strategies as strategy_store
from app.modules.quant.schemas import (
    QuantBacktestCreate,
    QuantBacktestList,
    QuantBacktestPayload,
    QuantBacktestRun,
    QuantSavedStrategy,
    QuantStrategyConfig,
    QuantStrategyConstraintDescriptor,
    QuantStrategyParameterDescriptor,
    QuantStrategyPreset,
    QuantStrategyRegistryStatus,
    QuantStrategySave,
)
from app.modules.quant.strategies.contracts import StrategySnapshot
from app.modules.quant.strategies.registry import get_strategy_registry

MAX_ACTIVE_RUNS_PER_USER = 2


def strategy_presets() -> list[QuantStrategyPreset]:
    presets: list[QuantStrategyPreset] = []
    for strategy in get_strategy_registry().descriptors():
        definition = strategy.definition
        parameters = [
            QuantStrategyParameterDescriptor(
                key=key,
                **parameter.model_dump(mode="json"),
            )
            for key, parameter in definition.parameters.items()
        ]
        config = QuantStrategyConfig(
            type=definition.key,
            version=definition.version,
            parameters={key: parameter.default for key, parameter in definition.parameters.items()},
        )
        presets.append(
            QuantStrategyPreset(
                key=definition.key,
                version=definition.version,
                definition_hash=strategy.definition_hash,
                name=definition.name,
                description=definition.description,
                scenario=definition.scenario,
                risk_level=definition.risk_level,
                presentation=definition.presentation.model_dump(mode="json"),
                parameters=parameters,
                constraints=[
                    QuantStrategyConstraintDescriptor(**constraint.model_dump(mode="python"))
                    for constraint in definition.constraints
                ],
                config=config,
            )
        )
    return presets


def strategy_registry_status() -> QuantStrategyRegistryStatus:
    status = get_strategy_registry().status
    return QuantStrategyRegistryStatus(
        directory=status.directory,
        published_directory=status.published_directory,
        ledger_path=status.ledger_path,
        generation=status.generation,
        loaded_at=status.loaded_at,
        last_attempt_at=status.last_attempt_at,
        last_error=status.last_error,
        strategy_count=status.strategy_count,
        latest_versions=dict(status.latest_versions),
    )


def _resolve_strategy(config: QuantStrategyConfig) -> StrategySnapshot:
    return get_strategy_registry().resolve(config.type, config.version, config.parameters)


def _snapshot_config(snapshot: StrategySnapshot) -> QuantStrategyConfig:
    return QuantStrategyConfig(
        type=snapshot.key,
        version=snapshot.version,
        name=snapshot.definition.name,
        parameters=snapshot.parameters,
    )


def _as_backtest_payload(request: QuantBacktestCreate | QuantBacktestPayload) -> QuantBacktestPayload:
    if isinstance(request, QuantBacktestPayload):
        return request
    return QuantBacktestPayload(**request.model_dump(mode="python"))


def _to_saved_strategy(row: strategy_store.SavedStrategyRow) -> QuantSavedStrategy:
    return QuantSavedStrategy(
        id=row.id,
        name=row.name,
        config=QuantStrategyConfig.model_validate(row.config),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def save_user_strategy(request: QuantStrategySave, user_id: int) -> QuantSavedStrategy:
    config = _snapshot_config(_resolve_strategy(request.config))
    row = await call_blocking(
        strategy_store.save_strategy,
        user_id,
        request.name.strip(),
        config.model_dump(mode="json"),
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


def _item_date(item: Any) -> str:
    value = item.get("date") if isinstance(item, dict) else getattr(item, "date", "")
    return str(value or "")


def _items_in_range(items: list[Any], start_date: str, end_date: str) -> list[Any]:
    return [
        item
        for item in items
        if (not start_date or _item_date(item) >= start_date)
        and (not end_date or _item_date(item) <= end_date)
    ]


def _normalize_bar_sets(
    bar_sets: list[HistoricalBarSet],
    start_date: str,
    warmup_bars: int,
) -> list[HistoricalBarSet]:
    required_prestart = warmup_bars + 1
    normalized = []
    for bar_set in bar_sets:
        by_date = {item.date: item for item in bar_set.items}
        ordered = [by_date[day] for day in sorted(by_date)]
        prestart = [item for item in ordered if item.date < start_date]
        if len(prestart) < required_prestart:
            raise ValueError(
                f"{bar_set.code} 预热行情不足: 需要 {required_prestart} 根，实际 {len(prestart)} 根"
            )
        items = [*prestart[-required_prestart:], *(item for item in ordered if item.date >= start_date)]
        normalized.append(replace(
            bar_set,
            data_hash=historical_bar_hash(bar_set.code, bar_set.period, bar_set.adjust, items),
            items=items,
        ))
    return normalized


def _result_with_market_snapshots(row: run_store.QuantRunRow) -> dict[str, Any] | None:
    if row.result is None:
        return None
    result = dict(row.result)
    if not row.input_snapshot:
        return result
    stocks = row.input_snapshot.get("stocks")
    if not isinstance(stocks, dict):
        return result
    metadata = row.input_snapshot.get("stock_metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    existing_snapshots = result.get("market_snapshots")
    existing_by_code = {
        str(item.get("code")): item
        for item in existing_snapshots
        if isinstance(item, dict) and item.get("code")
    } if isinstance(existing_snapshots, list) else {}
    start_date = str(row.request.get("start_date") or "")
    end_date = str(row.request.get("end_date") or "")
    requested_codes = (row.request.get("universe") or {}).get("codes") or []
    code_order = list(dict.fromkeys([*requested_codes, *stocks.keys()]))
    result["market_snapshots"] = [
        {
            "code": code,
            "source": str(
                (metadata.get(code) or {}).get("source")
                or (existing_by_code.get(code) or {}).get("source")
                or "backtest-input-snapshot"
            ),
            "data_hash": str(
                (metadata.get(code) or {}).get("data_hash")
                or (existing_by_code.get(code) or {}).get("data_hash")
                or ""
            ),
            "items": _items_in_range(
                [item for item in stocks.get(code, []) if isinstance(item, dict)],
                start_date,
                end_date,
            ),
        }
        for code in code_order
        if isinstance(stocks.get(code), list)
    ]
    return result


def _to_api(
    row: run_store.QuantRunRow,
    *,
    include_market_snapshots: bool = False,
) -> QuantBacktestRun:
    return QuantBacktestRun(
        id=row.id,
        name=row.name,
        status=row.status,
        request=QuantBacktestCreate.model_validate(row.request),
        result=_result_with_market_snapshots(row) if include_market_snapshots else row.result,
        error=row.last_error,
        attempts=row.attempts,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


async def _resolve_request(
    request: QuantBacktestCreate,
    user_id: int,
    *,
    strategy_snapshot: StrategySnapshot | None = None,
) -> QuantBacktestPayload:
    payload = request.model_copy(deep=True)
    if payload.end_date == date.today():
        payload.end_date = await get_completed_market_date(payload.end_date)
        if payload.end_date <= payload.start_date:
            raise ValueError("最近已完成交易日必须晚于开始日期")
    if payload.universe.source == "portfolio":
        payload.universe.codes = await list_held_stock_codes(user_id)
    payload.universe.codes = list(dict.fromkeys(
        normalize_code(code).raw for code in payload.universe.codes
    ))
    if not payload.universe.codes:
        raise ValueError("股票池不能为空")
    if len(payload.universe.codes) > 10:
        raise ValueError("股票池最多支持 10 只股票")
    payload.benchmark = normalize_index_code(payload.benchmark.strip().lower())
    if not payload.benchmark.isdigit() or len(payload.benchmark) != 6:
        raise ValueError("基准指数代码必须为 6 位数字")
    snapshot = strategy_snapshot or _resolve_strategy(payload.strategy)
    payload.strategy = _snapshot_config(snapshot)
    return QuantBacktestPayload(**{
        **payload.model_dump(mode="json"),
        "strategy_snapshot": snapshot,
    })


async def create_backtest(request: QuantBacktestCreate, user_id: int) -> QuantBacktestRun:
    resolved = await _resolve_request(request, user_id)
    return await _enqueue_backtest(resolved, user_id)


async def create_backtest_with_snapshot(
    request: QuantBacktestCreate,
    user_id: int,
    strategy_snapshot: StrategySnapshot,
) -> QuantBacktestRun:
    resolved = await _resolve_request(
        request,
        user_id,
        strategy_snapshot=strategy_snapshot,
    )
    return await _enqueue_backtest(resolved, user_id)


async def _enqueue_backtest(resolved: QuantBacktestPayload, user_id: int) -> QuantBacktestRun:
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
    return _to_api(row, include_market_snapshots=True) if row else None


async def list_backtests(user_id: int, *, limit: int = 50, offset: int = 0) -> QuantBacktestList:
    rows = await call_blocking(
        run_store.list_runs,
        user_id,
        limit=limit,
        offset=offset,
        semaphore=database_semaphore,
    )
    return QuantBacktestList(items=[_to_api(row) for row in rows])


async def execute_backtest(request: QuantBacktestCreate | QuantBacktestPayload) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = _as_backtest_payload(request)
    strategy_snapshot = payload.strategy_snapshot or _resolve_strategy(payload.strategy)
    warmup_bars = strategy_warmup_bars(strategy_snapshot)
    required_prestart_bars = warmup_bars + 1
    stock_history_start = payload.start_date - timedelta(
        days=required_prestart_bars * 2 + 14,
    )
    stock_history_task = asyncio.gather(
        *(
            get_historical_bars(
                code,
                stock_history_start,
                payload.end_date,
                period="daily",
                adjust="qfq",
            )
            for code in payload.universe.codes
        )
    )
    benchmark_task = asyncio.create_task(
        get_index_kline(
            payload.benchmark,
            period="daily",
            start_date=payload.start_date.isoformat(),
            end_date=payload.end_date.isoformat(),
        )
    )
    bar_sets, benchmark = await asyncio.gather(stock_history_task, benchmark_task)
    bar_sets = _normalize_bar_sets(bar_sets, payload.start_date.isoformat(), warmup_bars)
    benchmark_hash = historical_bar_hash(payload.benchmark, "daily", "", benchmark.items)
    result = await call_blocking(
        run_backtest,
        {bar_set.code: bar_set.items for bar_set in bar_sets},
        benchmark.items,
        strategy_snapshot,
        payload.execution,
        data_hashes=[*(bar_set.data_hash for bar_set in bar_sets), benchmark_hash],
        data_sources=[
            *(bar_set.source for bar_set in bar_sets),
            benchmark.source or "benchmark-provider-chain",
        ],
        evaluation_start_date=payload.start_date.isoformat(),
        evaluation_end_date=payload.end_date.isoformat(),
        semaphore=misc_semaphore,
    )
    input_snapshot = {
        "stocks": {
            bar_set.code: [item.model_dump(mode="json") for item in bar_set.items]
            for bar_set in bar_sets
        },
        "benchmark": [item.model_dump(mode="json") for item in benchmark.items],
        "stock_metadata": {
            bar_set.code: {"source": bar_set.source, "data_hash": bar_set.data_hash}
            for bar_set in bar_sets
        },
        "strategy": strategy_snapshot.model_dump(mode="json"),
    }
    return result.model_dump(mode="json"), input_snapshot


async def cancel_backtest(run_id: str, user_id: int) -> bool:
    return await call_blocking(run_store.cancel, user_id, run_id, semaphore=database_semaphore)


async def retry_backtest(run_id: str, user_id: int) -> bool:
    return await call_blocking(run_store.retry_failed, user_id, run_id, semaphore=database_semaphore)


async def delete_backtest(run_id: str, user_id: int) -> bool:
    return await call_blocking(run_store.delete_run, user_id, run_id, semaphore=database_semaphore)
