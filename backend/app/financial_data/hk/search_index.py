"""Persistent in-memory search index for Hong Kong stock security master data."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import time
from types import MappingProxyType
from typing import Protocol

import pandas as pd

from app.configuration.paths import DATA_DIR
from app.core.concurrency.rate_limiter import call_blocking, sina_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.infrastructure.persistence.json_storage import atomic_write_json
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_SNAPSHOT_VERSION = 1
_DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60
_DEFAULT_FILE_PATH = DATA_DIR / "hk_stock_search_index.json"
_CODE_PATTERN = re.compile(r"^(?:hk)?(\d{1,5})$", re.IGNORECASE)


class HKStockMasterProvider(Protocol):
    def fetch_hk_stocks_spot(self) -> pd.DataFrame: ...


@dataclass(frozen=True)
class HKStockSearchRecord:
    code: str
    name: str
    english_name: str | None = None


@dataclass(frozen=True)
class _SearchIndexEntry:
    record: HKStockSearchRecord
    normalized_name: str
    normalized_english_name: str


@dataclass(frozen=True)
class _SearchIndexState:
    records: tuple[HKStockSearchRecord, ...]
    entries: tuple[_SearchIndexEntry, ...]
    code_exact: Mapping[str, int]
    code_prefixes: Mapping[str, tuple[int, ...]]
    name_exact: Mapping[str, tuple[int, ...]]
    name_prefixes: Mapping[str, tuple[int, ...]]
    name_characters: Mapping[str, tuple[int, ...]]
    name_bigrams: Mapping[str, tuple[int, ...]]
    updated_at: float


def _first_text(row: pd.Series, *columns: str) -> str | None:
    for column in columns:
        value = row.get(column)
        if value is not None and not pd.isna(value):
            text = str(value).strip()
            if text:
                return text
    return None


def _normalize_code(value: object) -> str | None:
    match = _CODE_PATTERN.fullmatch(str(value or "").strip())
    if match is None:
        return None
    return match.group(1).zfill(5)


def _normalize_text(value: str) -> str:
    return "".join(value.casefold().split())


def _parse_updated_at(value: object) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


def _add_index_value(index: dict[str, list[int]], key: str, position: int) -> None:
    if key:
        index.setdefault(key, []).append(position)


def _freeze_index(index: dict[str, list[int]]) -> Mapping[str, tuple[int, ...]]:
    return MappingProxyType(
        {key: tuple(dict.fromkeys(positions)) for key, positions in index.items()}
    )


class HKStockSearchIndex:
    """Serve HK stock searches from a durable security-master snapshot."""

    def __init__(
        self,
        provider: HKStockMasterProvider | None = None,
        *,
        file_path: Path = _DEFAULT_FILE_PATH,
        max_age_seconds: float = _DEFAULT_MAX_AGE_SECONDS,
        now: Callable[[], float] = time,
    ) -> None:
        self._provider = provider
        self._file_path = file_path
        self._max_age_seconds = max_age_seconds
        self._now = now
        self._state: _SearchIndexState | None = None
        self._singleflight: AsyncSingleFlight[_SearchIndexState] = AsyncSingleFlight()
        self._refresh_task: asyncio.Task[None] | None = None

    @property
    def provider(self) -> HKStockMasterProvider:
        return self._provider or get_provider("sina_hk")

    async def search(self, query: str, *, limit: int = 8) -> list[HKStockSearchRecord]:
        keyword = _normalize_text(query)
        if not keyword or limit <= 0:
            return []

        state = await self._ensure_state()
        code_query = _normalize_code(keyword)
        raw_code_query = keyword.removeprefix("hk")
        code_prefix = raw_code_query if raw_code_query.isdigit() else None
        results: list[HKStockSearchRecord] = []
        seen: set[int] = set()

        def append_positions(positions: tuple[int, ...]) -> bool:
            for position in positions:
                if position in seen:
                    continue
                seen.add(position)
                results.append(state.records[position])
                if len(results) >= limit:
                    return True
            return False

        if code_query is not None:
            exact_position = state.code_exact.get(code_query)
            if exact_position is not None and append_positions((exact_position,)):
                return results
        if code_prefix is not None and append_positions(
            state.code_prefixes.get(code_prefix, ())
        ):
            return results
        if append_positions(state.name_exact.get(keyword, ())):
            return results
        if append_positions(state.name_prefixes.get(keyword, ())):
            return results

        contains_positions = tuple(
            position
            for position in self._contains_candidates(state, keyword)
            if self._matches_name_contains(state.entries[position], keyword)
        )
        append_positions(contains_positions)
        return results

    @staticmethod
    def _contains_candidates(
        state: _SearchIndexState,
        keyword: str,
    ) -> tuple[int, ...]:
        if len(keyword) == 1:
            return state.name_characters.get(keyword, ())
        candidate_groups = [
            state.name_bigrams.get(keyword[offset : offset + 2], ())
            for offset in range(len(keyword) - 1)
        ]
        if not candidate_groups or any(not group for group in candidate_groups):
            return ()
        return min(candidate_groups, key=len)

    @staticmethod
    def _matches_name_contains(entry: _SearchIndexEntry, keyword: str) -> bool:
        return keyword in entry.normalized_name or keyword in entry.normalized_english_name

    async def prewarm(self) -> None:
        await self._ensure_state()

    async def wait_for_refresh(self) -> None:
        """Wait for a scheduled stale snapshot refresh, mainly for orderly tests/shutdown."""
        task = self._refresh_task
        if task is not None:
            await asyncio.shield(task)

    async def _ensure_state(self) -> _SearchIndexState:
        state = self._state
        if state is None:
            state = await self._singleflight.do("build", self._load_or_fetch)
            self._state = state
        if self._is_stale(state):
            self._schedule_refresh()
        return state

    def _is_stale(self, state: _SearchIndexState) -> bool:
        return self._now() - state.updated_at >= self._max_age_seconds

    async def _load_or_fetch(self) -> _SearchIndexState:
        snapshot = self._load_snapshot()
        if snapshot is not None:
            return snapshot
        return await self._fetch_and_persist()

    def _load_snapshot(self) -> _SearchIndexState | None:
        try:
            payload = json.loads(self._file_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError):
            logger.warning("港股搜索索引快照读取失败，将从上游重建", exc_info=True)
            return None

        if not isinstance(payload, dict) or payload.get("version") != _SNAPSHOT_VERSION:
            return None
        updated_at = _parse_updated_at(payload.get("updated_at"))
        items = payload.get("items")
        if updated_at is None or not isinstance(items, list):
            return None
        records = self._records_from_items(items)
        if not records:
            return None
        return self._build_state(records, updated_at)

    async def _fetch_and_persist(self) -> _SearchIndexState:
        try:
            frame = await call_blocking(
                self.provider.fetch_hk_stocks_spot,
                semaphore=sina_semaphore,
            )
        except Exception as error:
            raise UpstreamUnavailableError("港股证券搜索索引暂时不可用") from error
        if not isinstance(frame, pd.DataFrame):
            raise UpstreamUnavailableError("新浪港股证券列表返回格式异常")

        records = self._records_from_frame(frame)
        if not records:
            raise UpstreamUnavailableError("新浪港股证券列表为空或格式异常")
        updated_at = self._now()
        payload = {
            "version": _SNAPSHOT_VERSION,
            "updated_at": datetime.fromtimestamp(updated_at, tz=UTC).isoformat(),
            "items": [
                {
                    "code": record.code,
                    "name": record.name,
                    "english_name": record.english_name,
                }
                for record in records
            ],
        }
        try:
            atomic_write_json(self._file_path, payload)
        except OSError:
            logger.warning("港股搜索索引快照写入失败，本次仍使用内存索引", exc_info=True)
        return self._build_state(records, updated_at)

    @staticmethod
    def _build_state(
        records: tuple[HKStockSearchRecord, ...],
        updated_at: float,
    ) -> _SearchIndexState:
        entries = tuple(
            _SearchIndexEntry(
                record=record,
                normalized_name=_normalize_text(record.name),
                normalized_english_name=_normalize_text(record.english_name or ""),
            )
            for record in records
        )
        code_exact: dict[str, int] = {}
        code_prefixes: dict[str, list[int]] = {}
        name_exact: dict[str, list[int]] = {}
        name_prefixes: dict[str, list[int]] = {}
        name_characters: dict[str, list[int]] = {}
        name_bigrams: dict[str, list[int]] = {}

        for position, entry in enumerate(entries):
            code = entry.record.code
            code_exact[code] = position
            unpadded_code = code.lstrip("0") or "0"
            for candidate in {code, unpadded_code}:
                for end in range(1, len(candidate) + 1):
                    _add_index_value(code_prefixes, candidate[:end], position)

            for normalized_name in {
                entry.normalized_name,
                entry.normalized_english_name,
            }:
                if not normalized_name:
                    continue
                _add_index_value(name_exact, normalized_name, position)
                for end in range(1, len(normalized_name) + 1):
                    _add_index_value(name_prefixes, normalized_name[:end], position)
                for character in set(normalized_name):
                    _add_index_value(name_characters, character, position)
                for offset in range(len(normalized_name) - 1):
                    _add_index_value(
                        name_bigrams,
                        normalized_name[offset : offset + 2],
                        position,
                    )

        return _SearchIndexState(
            records=records,
            entries=entries,
            code_exact=MappingProxyType(code_exact),
            code_prefixes=_freeze_index(code_prefixes),
            name_exact=_freeze_index(name_exact),
            name_prefixes=_freeze_index(name_prefixes),
            name_characters=_freeze_index(name_characters),
            name_bigrams=_freeze_index(name_bigrams),
            updated_at=updated_at,
        )

    @staticmethod
    def _records_from_frame(frame: pd.DataFrame) -> tuple[HKStockSearchRecord, ...]:
        items = [
            {
                "code": _first_text(row, "代码", "symbol", "code"),
                "name": _first_text(row, "中文名称", "名称", "name"),
                "english_name": _first_text(row, "英文名称", "engname", "english_name"),
            }
            for _, row in frame.iterrows()
        ]
        return HKStockSearchIndex._records_from_items(items)

    @staticmethod
    def _records_from_items(items: list[object]) -> tuple[HKStockSearchRecord, ...]:
        records_by_code: dict[str, HKStockSearchRecord] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            code = _normalize_code(item.get("code"))
            name_value = item.get("name")
            name = str(name_value).strip() if name_value is not None else ""
            if code is None or not name:
                continue
            english_value = item.get("english_name")
            english_name = str(english_value).strip() if english_value is not None else None
            records_by_code.setdefault(
                code,
                HKStockSearchRecord(code=code, name=name, english_name=english_name or None),
            )
        return tuple(records_by_code[code] for code in sorted(records_by_code))

    def _schedule_refresh(self) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            return
        self._refresh_task = asyncio.create_task(self._refresh())

    async def _refresh(self) -> None:
        try:
            state = await self._singleflight.do("refresh", self._fetch_and_persist)
        except Exception:
            logger.warning("港股搜索索引后台刷新失败，继续使用旧快照", exc_info=True)
            return
        self._state = state


hk_stock_search_index = HKStockSearchIndex()


async def prewarm_hk_stock_search_index() -> None:
    await hk_stock_search_index.prewarm()
