"""股票主营信息的持久化按需加载服务。"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import pandas as pd

from app.configuration.paths import DATA_DIR
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore, ths_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import InvalidRequestError, UpstreamUnavailableError
from app.core.market import is_a_share_code, is_hk_code, normalize_code
from app.financial_data.hk.service import normalize_hk_code
from app.financial_data.stock.profile.schemas import StockBusinessIntro
from app.infrastructure.persistence.file_lock import exclusive_file_lock
from app.infrastructure.persistence.json_storage import atomic_write_json
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_SNAPSHOT_VERSION = 1
_DEFAULT_DATA_DIR = DATA_DIR / "stock_business_intro"


class StockBusinessIntroProvider(Protocol):
    def fetch_stock_business_intro(self, code: str) -> pd.DataFrame: ...


class StockBusinessIntroService:
    """首次抓取主营信息并永久落盘，后续请求只读取股票快照。"""

    def __init__(
        self,
        provider: StockBusinessIntroProvider | None = None,
        *,
        data_dir: Path = _DEFAULT_DATA_DIR,
    ) -> None:
        self._provider = provider
        self._data_dir = data_dir
        self._singleflight: AsyncSingleFlight[StockBusinessIntro] = AsyncSingleFlight()

    @property
    def provider(self) -> StockBusinessIntroProvider:
        return self._provider or get_provider("ths")

    @staticmethod
    def _normalize_code(code: str) -> str:
        if is_hk_code(code):
            # 港股统一归一到 5 位补零，与 hk_market_service、组合等模块保持同一标识
            return normalize_hk_code(code)
        try:
            normalized = normalize_code(code).raw
        except ValueError as error:
            raise InvalidRequestError(str(error)) from error
        if not is_a_share_code(normalized):
            raise InvalidRequestError(f"无效 A 股代码: {normalized}")
        return normalized

    def _snapshot_path(self, code: str) -> Path:
        return self._data_dir / f"{code}.json"

    def _lock_path(self, code: str) -> Path:
        return self._data_dir / ".locks" / f"{code}.lock"

    def _read_snapshot(self, code: str) -> StockBusinessIntro | None:
        path = self._snapshot_path(code)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, TypeError, ValueError) as error:
            logger.warning("读取主营信息快照失败 code=%s path=%s error=%s", code, path, error)
            return None

        if not isinstance(payload, dict):
            return None
        items = payload.get("items")
        if (
            payload.get("version") != _SNAPSHOT_VERSION
            or payload.get("code") != code
            or payload.get("source") != "ths"
            or not isinstance(payload.get("fetched_at"), str)
            or not isinstance(items, dict)
            or not items
            or not all(
                isinstance(key, str) and key and isinstance(value, str) and value for key, value in items.items()
            )
        ):
            logger.warning("忽略无效主营信息快照 code=%s path=%s", code, path)
            return None
        return StockBusinessIntro(code=code, source="ths", items=dict(items))

    def _read_from_db(self, code: str) -> StockBusinessIntro | None:
        if self._data_dir != _DEFAULT_DATA_DIR:
            return None
        try:
            from app.modules.stock_profile.repository import get_record
            rec = get_record(code)
            if rec and rec.get("main_business"):
                db_items: dict[str, str] = {"主营业务": rec["main_business"]}
                if rec.get("business_scope"):
                    db_items["经营范围"] = rec["business_scope"]
                if rec.get("products"):
                    db_items["产品名称"] = rec["products"]
                return StockBusinessIntro(code=code, source="ths", items=db_items)
        except Exception as error:
            logger.debug("读取数据库主营信息失败 code=%s error=%s", code, error)
        return None

    def _write_snapshot(self, result: StockBusinessIntro) -> None:
        atomic_write_json(
            self._snapshot_path(result.code),
            {
                "version": _SNAPSHOT_VERSION,
                "code": result.code,
                "source": result.source,
                "fetched_at": datetime.now(UTC).isoformat(),
                "items": result.items,
            },
            indent=2,
        )
        if self._data_dir == _DEFAULT_DATA_DIR:
            try:
                from app.modules.code_normalization import normalize_stock_identity
                from app.modules.stock_profile.repository import (
                    ensure_basic_skeleton,
                    update_business_info,
                )

                full_code, exchange, market = normalize_stock_identity(result.code)
                main_business = result.items.get("主营业务", "")
                # 库里没有该股行时先建档，主营业务才能落进 stock_basic_profiles；
                # 已存在则 ensure 不改动任何字段，仍由 update_business_info 只补空值。
                ensure_basic_skeleton(
                    stock_code=full_code,
                    exchange=exchange,
                    market_group=market,
                    source="ths",
                )
                update_business_info(
                    full_code,
                    main_business=main_business,
                    business_scope=result.items.get("经营范围", ""),
                    products=result.items.get("产品名称") or result.items.get("产品类型") or "",
                    source="ths",
                )
            except Exception as error:
                logger.warning("同步主营信息至数据库失败 code=%s error=%s", result.code, error)

    @staticmethod
    def _from_frame(code: str, frame: pd.DataFrame) -> StockBusinessIntro:
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("同花顺主营信息返回类型无效")
        if frame.empty:
            raise UpstreamUnavailableError(f"同花顺未返回股票 {code} 的主营信息")

        row: Mapping = frame.iloc[0]
        items: dict[str, str] = {}
        for column, value in row.items():
            column_text = str(column).strip()
            if column_text == "股票代码" or value is None or pd.isna(value):
                continue
            value_text = str(value).strip()
            if column_text and value_text:
                items[column_text] = value_text
        if not items:
            raise UpstreamUnavailableError(f"同花顺未返回股票 {code} 的主营信息")
        return StockBusinessIntro(code=code, source="ths", items=items)

    def _load_and_persist_locked(self, code: str) -> StockBusinessIntro:
        with exclusive_file_lock(self._lock_path(code)):
            persisted = self._read_snapshot(code)
            if persisted is not None:
                return persisted
            from_db = self._read_from_db(code)
            if from_db is not None:
                return from_db
            frame = self.provider.fetch_stock_business_intro(code)
            result = self._from_frame(code, frame)
            self._write_snapshot(result)
            return result

    async def _load_and_persist(self, code: str) -> StockBusinessIntro:
        try:
            return await provider_gateway.call_blocking(
                "ths",
                "stock_business_intro",
                self._load_and_persist_locked,
                code,
                semaphore=ths_semaphore,
            )
        except UpstreamUnavailableError:
            raise
        except Exception as error:
            logger.warning("同花顺主营信息获取失败 code=%s error_type=%s", code, type(error).__name__)
            raise UpstreamUnavailableError(f"股票 {code} 的主营信息暂时不可用") from error

    async def get(self, code: str) -> StockBusinessIntro:
        normalized = self._normalize_code(code)
        persisted = await call_blocking(self._read_snapshot, normalized, semaphore=misc_semaphore)
        if persisted is not None:
            return persisted
        from_db = await call_blocking(self._read_from_db, normalized, semaphore=misc_semaphore)
        if from_db is not None:
            return from_db
        return await self._singleflight.do(
            normalized,
            lambda: self._load_and_persist(normalized),
        )


_business_intro_service = StockBusinessIntroService()


async def get_stock_business_intro(code: str) -> StockBusinessIntro:
    """获取股票主营信息；已有本地快照时不访问上游。"""
    return await _business_intro_service.get(code)
