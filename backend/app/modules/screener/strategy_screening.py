"""Apply bundled deterministic Quant strategies to Screener candidates."""

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from typing import cast

from app.core.cache import TTLCache
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.financial_data.stock.public import get_historical_bars
from app.modules.quant.public import StrategySnapshot, build_target_positions, get_strategy_registry, strategy_presets
from app.modules.screener.schemas import (
    ScreenerStrategyMatch,
    ScreenerStrategyPreset,
    ScreenerStrategyRequest,
    ScreenerStrategyResult,
)

SCREENER_STRATEGY_KEYS = frozenset({
    "bull_trend",
    "ma_golden_cross",
    "volume_breakout",
    "shrink_pullback",
    "bottom_volume",
    "one_yang_three_yin",
    "box_oscillation",
})
_MAX_CONCURRENCY = 5
MAX_STRATEGY_CANDIDATES = 200
_STRATEGY_CACHE_TTL_SECONDS = 300
_strategy_cache = TTLCache(maxsize=256, name="screener_strategy")
_strategy_singleflight: AsyncSingleFlight[ScreenerStrategyResult] = AsyncSingleFlight()


def _latest_entry_index(positions: list[int]) -> int | None:
    for index in range(len(positions) - 1, -1, -1):
        if positions[index] == 1 and (index == 0 or positions[index - 1] != 1):
            return index
    return None


def list_screener_strategies() -> list[ScreenerStrategyPreset]:
    return [
        ScreenerStrategyPreset(
            key=preset.key,
            name=preset.name,
            description=preset.description,
            scenario=preset.scenario,
            risk_level=preset.risk_level,
            parameters=dict(preset.config.parameters or {}),
            parameter_definitions=[definition.model_dump() for definition in preset.parameters],
        )
        for preset in strategy_presets()
        if preset.key in SCREENER_STRATEGY_KEYS
    ]


def _resolve_screener_strategy(request: ScreenerStrategyRequest) -> StrategySnapshot:
    if request.strategy_key not in SCREENER_STRATEGY_KEYS:
        raise ValueError(f"不支持的选股策略: {request.strategy_key}")
    return get_strategy_registry().resolve(request.strategy_key, request.version, request.parameters)


def validate_screener_strategy_request(request: ScreenerStrategyRequest) -> None:
    _resolve_screener_strategy(request)


async def screen_candidates_by_strategy(
    request: ScreenerStrategyRequest,
    progress_callback: Callable[[dict], Awaitable[None]] | None = None,
) -> ScreenerStrategyResult:
    snapshot = _resolve_screener_strategy(request)
    normalized_codes = list(dict.fromkeys(code.strip() for code in request.codes if code.strip()))
    if not normalized_codes:
        raise ValueError("候选股票代码不能为空")
    end_date = date.today()
    cache_payload = json.dumps({
        "hash": snapshot.definition_hash,
        "parameters": snapshot.parameters,
        "codes": normalized_codes,
        "lookback_days": request.lookback_days,
        "date": end_date.isoformat(),
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    cache_key = hashlib.sha256(cache_payload.encode()).hexdigest()
    cached = _strategy_cache.get(cache_key)
    if isinstance(cached, ScreenerStrategyResult):
        return cached

    async def load() -> ScreenerStrategyResult:
        start_date = end_date - timedelta(days=request.lookback_days)
        semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
        matches: list[ScreenerStrategyMatch] = []
        failed: dict[str, str] = {}

        completed = 0
        completed_lock = asyncio.Lock()

        async def evaluate(code: str) -> None:
            nonlocal completed
            async with semaphore:
                try:
                    bars = await get_historical_bars(code, start_date, end_date, period="daily", adjust="qfq")
                    if not bars.items:
                        raise ValueError("无可用历史行情")
                    positions = build_target_positions(bars.items, snapshot)
                    if len(positions) != len(bars.items):
                        raise RuntimeError("策略仓位序列与历史行情长度不一致")
                    if positions and positions[-1] == 1:
                        entry_index = _latest_entry_index(positions)
                        if entry_index is None:
                            raise RuntimeError("策略持仓状态缺少入场信号")
                        matches.append(ScreenerStrategyMatch(
                            code=code,
                            signal_date=bars.items[entry_index].date,
                            target_position=1,
                            data_source=str(getattr(bars, "source", "") or ""),
                            data_hash=str(getattr(bars, "data_hash", "") or ""),
                            used_fallback="fallback" in str(getattr(bars, "source", "")).lower(),
                        ))
                except Exception as error:
                    failed[code] = str(error) or type(error).__name__
                finally:
                    async with completed_lock:
                        completed += 1
                        if progress_callback is not None:
                            await progress_callback({
                                "type": "progress",
                                "completed": completed,
                                "total": len(normalized_codes),
                                "matched": len(matches),
                                "failed": len(failed),
                            })

        await asyncio.gather(*(evaluate(code) for code in normalized_codes))
        if len(failed) == len(normalized_codes):
            raise RuntimeError("全部候选股票历史数据获取失败")
        result = ScreenerStrategyResult(
            strategy_key=snapshot.key,
            strategy_name=snapshot.definition.name,
            strategy_version=snapshot.version,
            definition_hash=snapshot.definition_hash,
            parameters=dict(snapshot.parameters),
            matches=[match for code in normalized_codes for match in matches if match.code == code],
            matched_codes=[code for code in normalized_codes if code in {match.code for match in matches}],
            evaluated=len(normalized_codes),
            failed=failed,
            fallback_count=sum(1 for match in matches if match.used_fallback),
        )
        if not failed:
            _strategy_cache.set(cache_key, result, _STRATEGY_CACHE_TTL_SECONDS)
        return result

    if progress_callback is not None:
        return await load()
    return cast(ScreenerStrategyResult, await _strategy_singleflight.do(cache_key, load))
