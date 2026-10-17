"""上海黄金交易所历史行情的按日快照服务。"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

from app.configuration.paths import DATA_DIR
from app.core.concurrency.rate_limiter import call_blocking, exchange_semaphore, misc_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import InvalidRequestError, UpstreamUnavailableError
from app.core.parsing import coerce_finite_float
from app.core.timezones import SHANGHAI_TIMEZONE
from app.financial_data.market.macro.schemas import SgeGoldHistoryPoint, SgeGoldResponse
from app.infrastructure.persistence.file_lock import exclusive_file_lock
from app.infrastructure.persistence.json_storage import atomic_write_json
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_SNAPSHOT_VERSION = 1
_SOURCE = "上海黄金交易所"
# 最新交易日滞后超过该天数即视为合约停止交易。
# 上金所行情按交易日更新，正常情况下滞后最多几个自然日（长假会更长），
# 因此阈值取 10 天：既能识别停更合约，又不会被长假误判。
_DELISTED_STALE_DAYS = 10

# slug 同时用于快照文件名，显式映射可避免括号、加号等字符进入路径。
_SGE_SYMBOLS: dict[str, tuple[str, str, str]] = {
    "Au99.99": ("黄金 Au99.99", "元/克", "au99_99"),
    "Au99.95": ("黄金 Au99.95", "元/克", "au99_95"),
    "Au100g": ("黄金 Au100g", "元/克", "au100g"),
    "Pt99.95": ("铂金 Pt99.95", "元/克", "pt99_95"),
    "Ag(T+D)": ("白银 Ag(T+D)", "元/千克", "ag_td"),
    "Au(T+D)": ("黄金 Au(T+D)", "元/克", "au_td"),
    "mAu(T+D)": ("迷你黄金 mAu(T+D)", "元/克", "mau_td"),
    "Au(T+N1)": ("黄金 Au(T+N1)", "元/克", "au_tn1"),
    "Au(T+N2)": ("黄金 Au(T+N2)", "元/克", "au_tn2"),
    "Ag99.99": ("白银 Ag99.99", "元/千克", "ag99_99"),
    "iAu99.99": ("国际板黄金 iAu99.99", "元/克", "iau99_99"),
    "Au99.5": ("黄金 Au99.5", "元/克", "au99_5"),
    "iAu100g": ("国际板黄金 iAu100g", "元/克", "iau100g"),
    "iAu99.5": ("国际板黄金 iAu99.5", "元/克", "iau99_5"),
    "PGC30g": ("熊猫金币 PGC30g", "元/克", "pgc30g"),
    "NYAuTN06": ("沪纽金 NYAuTN06", "元/克", "nya_utn06"),
    "NYAuTN12": ("沪纽金 NYAuTN12", "元/克", "nya_utn12"),
}


class SgeGoldProvider(Protocol):
    def fetch(self, symbol: str) -> Mapping[str, Any]: ...


def _parse_date(value: Any) -> str | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _parse_history(payload: Mapping[str, Any]) -> list[dict[str, float | str]]:
    rows = payload.get("time")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("上金所返回数据缺少 time 字段")

    by_date: dict[str, dict[str, float | str]] = {}
    for row in rows:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) < 5:
            continue
        date = _parse_date(row[0])
        open_price, close, low, high = (coerce_finite_float(row[index]) for index in range(1, 5))
        if date is None or None in (open_price, close, low, high):
            continue
        by_date[date] = {
            "date": date,
            "open": open_price,
            "close": close,
            "low": low,
            "high": high,
        }
    history = [by_date[date] for date in sorted(by_date)]
    if not history:
        raise ValueError("上金所未返回有效历史行情")
    return history


class SgeGoldService:
    """按品种保存每日快照，并在刷新失败时返回最近一次有效数据。"""

    def __init__(
        self,
        provider: SgeGoldProvider | None = None,
        *,
        data_dir: Path = DATA_DIR,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider = provider if provider is not None else get_provider("sge")
        self._snapshot_dir = data_dir / "sge_gold"
        self._now = now or (lambda: datetime.now(SHANGHAI_TIMEZONE))
        self._singleflight: AsyncSingleFlight[SgeGoldResponse] = AsyncSingleFlight()

    @staticmethod
    def _validate_symbol(symbol: str) -> str:
        normalized = symbol.strip()
        if normalized not in _SGE_SYMBOLS:
            raise InvalidRequestError(f"不支持的上金所品种: {normalized or symbol}")
        return normalized

    def _snapshot_path(self, symbol: str) -> Path:
        return self._snapshot_dir / f"{_SGE_SYMBOLS[symbol][2]}.json"

    def _lock_path(self, symbol: str) -> Path:
        return self._snapshot_dir / ".locks" / f"{_SGE_SYMBOLS[symbol][2]}.lock"

    def _now_shanghai(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            return value.replace(tzinfo=SHANGHAI_TIMEZONE)
        return value.astimezone(SHANGHAI_TIMEZONE)

    def _read_snapshot(self, symbol: str) -> tuple[str, list[dict[str, float | str]]] | None:
        path = self._snapshot_path(symbol)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, TypeError, ValueError) as error:
            logger.warning("读取上金所快照失败 symbol=%s path=%s error_type=%s", symbol, path, type(error).__name__)
            return None
        if not isinstance(payload, Mapping):
            return None
        try:
            fetched_at = str(payload["fetched_at"])
            datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            history = _parse_history({"time": [
                [item.get("date"), item.get("open"), item.get("close"), item.get("low"), item.get("high")]
                for item in payload.get("history", [])
                if isinstance(item, Mapping)
            ]})
        except (KeyError, TypeError, ValueError):
            logger.warning("忽略无效上金所快照 symbol=%s path=%s", symbol, path)
            return None
        if payload.get("version") != _SNAPSHOT_VERSION or payload.get("symbol") != symbol:
            return None
        return fetched_at, history

    def _is_fresh(self, fetched_at: str) -> bool:
        try:
            fetched = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=SHANGHAI_TIMEZONE)
        return fetched.astimezone(SHANGHAI_TIMEZONE).date() == self._now_shanghai().date()

    def _to_response(
        self,
        symbol: str,
        fetched_at: str,
        raw_history: list[dict[str, float | str]],
        *,
        is_stale: bool,
    ) -> SgeGoldResponse:
        points: list[SgeGoldHistoryPoint] = []
        previous_close: float | None = None
        for row in raw_history:
            close = float(row["close"])
            change = None if previous_close is None else close - previous_close
            change_pct = None if change is None or previous_close == 0 else change / previous_close * 100
            points.append(
                SgeGoldHistoryPoint(
                    date=str(row["date"]),
                    open=float(row["open"]),
                    close=close,
                    low=float(row["low"]),
                    high=float(row["high"]),
                    change=change,
                    change_pct=change_pct,
                )
            )
            previous_close = close
        name, unit, _ = _SGE_SYMBOLS[symbol]
        return SgeGoldResponse(
            symbol=symbol,
            name=name,
            unit=unit,
            source=_SOURCE,
            latest=points[-1] if points else None,
            history=points,
            updated_at=fetched_at,
            is_stale=is_stale,
            is_delisted=self._is_delisted(points),
        )

    def _is_delisted(self, points: list[SgeGoldHistoryPoint]) -> bool:
        """最新交易日滞后超过阈值即视为合约已停止交易。"""
        if not points:
            return False
        try:
            latest = date.fromisoformat(points[-1].date)
        except ValueError:
            return False
        return (self._now_shanghai().date() - latest).days > _DELISTED_STALE_DAYS

    def _write_snapshot(self, symbol: str, fetched_at: str, history: list[dict[str, float | str]]) -> None:
        atomic_write_json(
            self._snapshot_path(symbol),
            {
                "version": _SNAPSHOT_VERSION,
                "symbol": symbol,
                "fetched_at": fetched_at,
                "history": history,
            },
            indent=2,
        )

    def _refresh_locked(self, symbol: str) -> SgeGoldResponse:
        with exclusive_file_lock(self._lock_path(symbol)):
            snapshot = self._read_snapshot(symbol)
            if snapshot is not None and self._is_fresh(snapshot[0]):
                return self._to_response(symbol, *snapshot, is_stale=False)
            try:
                history = _parse_history(
                    provider_gateway.call_sync(
                        "sge",
                        "fetch_gold_history",
                        lambda: self._provider.fetch(symbol),
                        # 上金所 403 属于频率限制，退避重试可恢复；重试预算需覆盖
                        # 单次 10s 最小间隔，故不沿用全局默认预算。
                        max_attempts=3,
                        retry_budget_seconds=45.0,
                    )
                )
            except Exception as error:
                if snapshot is not None:
                    logger.warning(
                        "上金所行情刷新失败，回退历史快照 symbol=%s error_type=%s",
                        symbol,
                        type(error).__name__,
                    )
                    return self._to_response(symbol, *snapshot, is_stale=True)
                raise UpstreamUnavailableError(f"上金所行情暂时不可用: {symbol}") from error
            fetched_at = self._now_shanghai().isoformat()
            self._write_snapshot(symbol, fetched_at, history)
            return self._to_response(symbol, fetched_at, history, is_stale=False)

    async def get(self, symbol: str = "Au99.99") -> SgeGoldResponse:
        normalized = self._validate_symbol(symbol)
        snapshot = await call_blocking(self._read_snapshot, normalized, semaphore=misc_semaphore)
        if snapshot is not None and self._is_fresh(snapshot[0]):
            return self._to_response(normalized, *snapshot, is_stale=False)
        return await self._singleflight.do(
            normalized,
            lambda: call_blocking(self._refresh_locked, normalized, semaphore=exchange_semaphore),
        )


_sge_gold_service = SgeGoldService()


async def get_sge_gold_history(symbol: str = "Au99.99") -> SgeGoldResponse:
    return await _sge_gold_service.get(symbol)


async def warm_up_sge_gold_snapshots(symbols: Sequence[str] | None = None) -> dict[str, int]:
    """预热全部品种的每日快照。

    上金所有严格频率限制（串行 5s 间隔），冷启动下逐个点击切换会把全部请求
    排到队列末尾，首个用户等待可达 80 秒以上。这里主动串行预热一次，
    之后所有品种都命中本地快照，页面秒开。

    Param:
        symbols: 待预热的品种；默认覆盖 _SGE_SYMBOLS 全部品种
    Return:
        dict: {"succeeded": 成功数, "failed": 失败数}
    """
    targets = list(symbols) if symbols is not None else list(_SGE_SYMBOLS)
    succeeded = 0
    failed = 0
    for symbol in targets:
        if symbol not in _SGE_SYMBOLS:
            logger.warning("跳过不支持的上金所品种: %s", symbol)
            continue
        try:
            await _sge_gold_service.get(symbol)
            succeeded += 1
        except Exception as error:
            failed += 1
            logger.warning(
                "上金所快照预热失败 symbol=%s error_type=%s error=%s",
                symbol,
                type(error).__name__,
                error,
            )
    logger.info("上金所快照预热完成: succeeded=%s failed=%s total=%s", succeeded, failed, len(targets))
    return {"succeeded": succeeded, "failed": failed}
