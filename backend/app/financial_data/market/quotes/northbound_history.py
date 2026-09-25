"""北向资金与沪深 300 历史数据快照服务。"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from app.configuration.paths import DATA_DIR
from app.core.concurrency.rate_limiter import call_blocking, exchange_semaphore, misc_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.financial_data.market.quotes.schemas import NorthboundHistoryPoint, NorthboundHistoryResponse
from app.infrastructure.persistence.file_lock import exclusive_file_lock
from app.infrastructure.persistence.json_storage import atomic_write_json
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
# v2: 金额单位从错误的"亿元(按万元换算)"修正为百万元口径 ÷100，旧快照作废
_SNAPSHOT_VERSION = 2
_LEGULEGU_SOURCE = "乐咕乐股"
_EASTMONEY_SOURCE = "东方财富"
_EASTMONEY_PAGE_SIZE = 2000
_EASTMONEY_MAX_PAGES = 2


class NorthboundHistoryProvider(Protocol):
    def fetch_northbound_history(self) -> Mapping[str, Any]: ...


class EastMoneyNorthboundProvider(Protocol):
    def fetch_datacenter_report(self, **kwargs: Any) -> list[dict[str, Any]]: ...

    def fetch_index_kline(self, **kwargs: Any) -> Any: ...


def _number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _date_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _find_feature_rows(payload: Any, predicate: Callable[[Mapping[str, Any]], bool]) -> list[Mapping[str, Any]]:
    candidates: list[list[Mapping[str, Any]]] = []

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            for child in value.values():
                visit(child)
            return
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return
        rows = [item for item in value if isinstance(item, Mapping) and predicate(item)]
        if rows:
            candidates.append(rows)
        for child in value:
            visit(child)

    visit(payload)
    return max(candidates, key=len, default=[])


def _northbound_row(row: Mapping[str, Any]) -> bool:
    return "date" in row and any(
        key in row
        for key in ("northMoney", "amountHongKongToSH", "amountHongKongToSZ")
    )


def _hs300_row(row: Mapping[str, Any]) -> bool:
    code = str(row.get("tsCode") or "").upper()
    return "tradeDate" in row and "close" in row and (not code or code == "000300.SH")


def _hs300_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """优先读顶层 indexDailies（真实上游布局），退化到形状探测兜底。"""
    direct = payload.get("indexDailies")
    if isinstance(direct, Sequence) and not isinstance(direct, (str, bytes)):
        rows = [item for item in direct if isinstance(item, Mapping) and _hs300_row(item)]
        if rows:
            return rows
    return _find_feature_rows(payload, _hs300_row)


def _mn_to_yi(value: Any) -> float | None:
    """上游金额单位为百万元（与东财 RPT_MUTUAL_DEAL_HISTORY 的 DEAL_AMT 同值
    交叉验证；2024-08-19 起该表公布成交总额），÷100 换算为亿元。"""
    parsed = _number(value)
    return None if parsed is None else parsed / 100


def _parse_items(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    north_rows = _find_feature_rows(payload, _northbound_row)
    index_rows = _hs300_rows(payload)

    for row in north_rows:
        date = _date_text(row.get("date"))
        if date is None:
            continue
        by_date[date] = {
            "date": date,
            "north_money": _mn_to_yi(row.get("northMoney")),
            "sh_connect": _mn_to_yi(row.get("amountHongKongToSH")),
            "sz_connect": _mn_to_yi(row.get("amountHongKongToSZ")),
            "south_money": _mn_to_yi(row.get("southMoney")),
        }

    for row in index_rows:
        date = _date_text(row.get("tradeDate"))
        if date is None:
            continue
        item = by_date.setdefault(date, {"date": date})
        item.update(
            {
                "hs300_open": _number(row.get("open")),
                "hs300_close": _number(row.get("close")),
                "hs300_high": _number(row.get("high")),
                "hs300_low": _number(row.get("low")),
                "hs300_change": _number(row.get("change")),
                "hs300_change_pct": _number(row.get("pctChg")),
            }
        )

    items = [by_date[date] for date in sorted(by_date)]
    # 沪深300 行缺失时仅丢弃 hs300_* 字段（schema 可空），不能让北向数据整体失败
    if not items or not north_rows:
        raise ValueError("乐咕乐股未返回有效的北向资金数据")
    return items


def _records(value: Any) -> list[Mapping[str, Any]]:
    """将 DataFrame 或普通行列表统一成字典列表，便于隔离 provider 类型。"""
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        value = to_dict(orient="records")
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _parse_eastmoney_items(
    north_rows: Sequence[Mapping[str, Any]],
    index_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for row in north_rows:
        if str(row.get("MUTUAL_TYPE") or "") != "005":
            continue
        date = _date_text(row.get("TRADE_DATE"))
        north_money = _mn_to_yi(row.get("DEAL_AMT"))
        if date is None or north_money is None:
            continue
        by_date[date] = {"date": date, "north_money": north_money}

    if not by_date:
        raise ValueError("东方财富未返回有效的北向资金数据")

    for row in index_rows:
        date = _date_text(row.get("date"))
        if date not in by_date:
            continue
        by_date[date].update(
            {
                "hs300_open": _number(row.get("open")),
                "hs300_close": _number(row.get("close")),
                "hs300_high": _number(row.get("high")),
                "hs300_low": _number(row.get("low")),
                "hs300_change": _number(row.get("change")),
                "hs300_change_pct": _number(row.get("change_pct")),
            }
        )
    return [by_date[date] for date in sorted(by_date)]


class NorthboundHistoryService:
    """保存每日快照，并在刷新失败时回退最近一次有效数据。"""

    def __init__(
        self,
        provider: NorthboundHistoryProvider | None = None,
        *,
        fallback_provider: EastMoneyNorthboundProvider | None = None,
        data_dir: Path = DATA_DIR,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider = provider if provider is not None else get_provider("legulegu")
        self._fallback_provider = (
            fallback_provider
            if fallback_provider is not None
            else get_provider("eastmoney") if provider is None else None
        )
        self._snapshot_path = data_dir / "legulegu" / "northbound_history.json"
        self._lock_path = data_dir / "legulegu" / ".locks" / "northbound_history.lock"
        self._now = now or (lambda: datetime.now(_SHANGHAI_TZ))
        self._singleflight: AsyncSingleFlight[NorthboundHistoryResponse] = AsyncSingleFlight()

    def _now_shanghai(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            return value.replace(tzinfo=_SHANGHAI_TZ)
        return value.astimezone(_SHANGHAI_TZ)

    def _is_fresh(self, fetched_at: str) -> bool:
        try:
            fetched = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=_SHANGHAI_TZ)
        return fetched.astimezone(_SHANGHAI_TZ).date() == self._now_shanghai().date()

    def _read_snapshot(self) -> tuple[str, str, list[NorthboundHistoryPoint]] | None:
        try:
            payload = json.loads(self._snapshot_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, TypeError, ValueError) as error:
            logger.warning("读取乐咕乐股快照失败 path=%s error_type=%s", self._snapshot_path, type(error).__name__)
            return None
        if not isinstance(payload, Mapping) or payload.get("version") != _SNAPSHOT_VERSION:
            return None
        try:
            fetched_at = str(payload["fetched_at"])
            datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            source = str(payload.get("source") or _LEGULEGU_SOURCE)
            if source not in {_LEGULEGU_SOURCE, _EASTMONEY_SOURCE}:
                return None
            raw_items = payload["items"]
            if not isinstance(raw_items, list) or not raw_items:
                return None
            items = [NorthboundHistoryPoint.model_validate(item) for item in raw_items]
        except (KeyError, TypeError, ValueError):
            logger.warning("忽略无效乐咕乐股快照 path=%s", self._snapshot_path)
            return None
        return source, fetched_at, items

    @staticmethod
    def _to_response(
        source: str,
        fetched_at: str,
        items: list[NorthboundHistoryPoint],
        page_size: int,
        *,
        is_stale: bool,
    ) -> NorthboundHistoryResponse:
        return NorthboundHistoryResponse(
            source=source,
            updated_at=fetched_at,
            is_stale=is_stale,
            items=items[-page_size:],
        )

    def _write_snapshot(self, source: str, fetched_at: str, items: list[NorthboundHistoryPoint]) -> None:
        atomic_write_json(
            self._snapshot_path,
            {
                "version": _SNAPSHOT_VERSION,
                "source": source,
                "fetched_at": fetched_at,
                "items": [item.model_dump(mode="json") for item in items],
            },
            indent=2,
        )

    def _fetch_eastmoney_items(self) -> list[NorthboundHistoryPoint]:
        if self._fallback_provider is None:
            raise RuntimeError("未配置北向资金备用数据源")

        north_rows: list[Mapping[str, Any]] = []
        page_number = 1
        while True:
            page_rows = provider_gateway.call_sync(
                "eastmoney",
                "fetch_northbound_history",
                lambda: self._fallback_provider.fetch_datacenter_report(
                    report_name="RPT_MUTUAL_DEAL_HISTORY",
                    columns="MUTUAL_TYPE,TRADE_DATE,DEAL_AMT",
                    filter_str='(MUTUAL_TYPE="005")',
                    page_size=_EASTMONEY_PAGE_SIZE,
                    page_number=page_number,
                    sort_columns="TRADE_DATE",
                    sort_types="-1",
                ),
                is_fallback_attempt=True,
            )
            north_rows.extend(_records(page_rows))
            if len(page_rows) < _EASTMONEY_PAGE_SIZE or page_number >= _EASTMONEY_MAX_PAGES:
                break
            page_number += 1

        parsed_items = _parse_eastmoney_items(north_rows, [])
        start_date = parsed_items[0]["date"].replace("-", "")
        end_date = self._now_shanghai().date().strftime("%Y%m%d")
        index_rows: list[Mapping[str, Any]] = []
        try:
            index_frame = provider_gateway.call_sync(
                "eastmoney",
                "fetch_index_kline",
                lambda: self._fallback_provider.fetch_index_kline(
                    symbol="000300",
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                ),
                is_fallback_attempt=True,
            )
            index_rows = _records(index_frame)
        except Exception as error:
            logger.warning("东方财富沪深300历史刷新失败 error_type=%s", type(error).__name__)

        raw_items = _parse_eastmoney_items(north_rows, index_rows)
        return [NorthboundHistoryPoint.model_validate(item) for item in raw_items]

    def _refresh_locked(self, page_size: int) -> NorthboundHistoryResponse:
        with exclusive_file_lock(self._lock_path):
            snapshot = self._read_snapshot()
            if snapshot is not None and self._is_fresh(snapshot[1]):
                return self._to_response(*snapshot, page_size, is_stale=False)
            try:
                raw_items = _parse_items(
                    provider_gateway.call_sync(
                        "legulegu",
                        "fetch_northbound_history",
                        self._provider.fetch_northbound_history,
                    )
                )
                items = [NorthboundHistoryPoint.model_validate(item) for item in raw_items]
                source = _LEGULEGU_SOURCE
            except Exception as primary_error:
                logger.warning("乐咕乐股刷新失败，尝试东方财富 error_type=%s", type(primary_error).__name__)
                try:
                    items = self._fetch_eastmoney_items()
                    source = _EASTMONEY_SOURCE
                except Exception as fallback_error:
                    if snapshot is not None:
                        logger.warning(
                            "北向资金实时刷新失败，回退历史快照 primary_error_type=%s fallback_error_type=%s",
                            type(primary_error).__name__,
                            type(fallback_error).__name__,
                        )
                        return self._to_response(*snapshot, page_size, is_stale=True)
                    raise UpstreamUnavailableError("北向资金历史数据暂时不可用") from fallback_error
            fetched_at = self._now_shanghai().isoformat()
            self._write_snapshot(source, fetched_at, items)
            return self._to_response(source, fetched_at, items, page_size, is_stale=False)

    async def get(self, page_size: int = 500) -> NorthboundHistoryResponse:
        snapshot = await call_blocking(self._read_snapshot, semaphore=misc_semaphore)
        if snapshot is not None and self._is_fresh(snapshot[1]):
            return self._to_response(*snapshot, page_size, is_stale=False)
        return await self._singleflight.do(
            "northbound_history",
            lambda: call_blocking(self._refresh_locked, page_size, semaphore=exchange_semaphore),
        )


_northbound_history_service = NorthboundHistoryService()


async def get_northbound_history(page_size: int = 500) -> NorthboundHistoryResponse:
    return await _northbound_history_service.get(page_size)
