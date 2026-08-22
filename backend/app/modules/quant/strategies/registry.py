"""量化策略的不可变快照注册表。"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import Mapping, cast

import yaml

from app.infrastructure.persistence.json_storage import atomic_write_json, atomic_write_text, durable_unlink
from app.modules.quant.strategies.compiler import CompiledStrategy, compile_strategy
from app.modules.quant.strategies.contracts import (
    NumericValue,
    ParameterValue,
    StrategyDefinition,
    StrategyParameterConstraint,
    StrategyParameterDefinition,
    StrategySnapshot,
)
from app.modules.quant.strategies.loader import (
    canonical_definition_hash,
    load_strategy_definitions_from_directories,
)

DEFAULT_STRATEGY_DIRECTORY = Path(__file__).resolve().parent / "definitions"
MAX_INDICATOR_PERIOD = 10_000
MAX_INDICATOR_OFFSET = 10_000
HASH_LEDGER_SCHEMA_VERSION = 1
_DEFINITION_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_STRATEGY_IDENTITY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}@[0-9]+\.[0-9]+\.[0-9]+$")

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StrategyRegistryState:
    strategies: Mapping[tuple[str, str], CompiledStrategy]
    latest_versions: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class StrategyRegistryStatus:
    directory: str
    published_directory: str | None
    ledger_path: str | None
    generation: int
    loaded_at: float | None
    last_attempt_at: float | None
    last_error: str | None
    strategy_count: int
    latest_versions: Mapping[str, str]


_EMPTY_STATE = StrategyRegistryState(MappingProxyType({}), MappingProxyType({}))


def _version_key(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def _matches(value: ParameterValue, definition: StrategyParameterDefinition) -> bool:
    if definition.type == "integer":
        return type(value) is int
    if definition.type == "number":
        return type(value) in (int, float)
    if definition.type == "boolean":
        return type(value) is bool
    return type(value) is str


def _compare(operator: str, left: NumericValue, right: NumericValue) -> bool:
    if operator == "greater_than":
        return left > right
    if operator == "greater_or_equal":
        return left >= right
    if operator == "less_than":
        return left < right
    return left <= right


def _constraint_operand(value: int | float | str, parameters: dict[str, ParameterValue]) -> NumericValue:
    if isinstance(value, str) and value.startswith("$"):
        resolved = parameters[value[1:]]
        if type(resolved) not in (int, float):
            raise ValueError(f"策略约束参数必须是数值: {value[1:]}")
        return cast(NumericValue, resolved)
    if isinstance(value, str):
        raise ValueError("策略约束只能使用参数引用或数值字面量")
    return value


def _validate_constraint(
    constraint: StrategyParameterConstraint,
    parameters: dict[str, ParameterValue],
) -> None:
    left = _constraint_operand(constraint.left, parameters)
    right = _constraint_operand(constraint.right, parameters)
    if not _compare(constraint.operator, left, right):
        raise ValueError(constraint.message)


def _integer_argument(value: int | str, parameters: dict[str, ParameterValue]) -> int:
    resolved = parameters[value[1:]] if isinstance(value, str) and value.startswith("$") else value
    return int(resolved)


def _ledger_identity(identity: tuple[str, str]) -> str:
    return f"{identity[0]}@{identity[1]}"


def _load_hash_ledger(path: Path | None) -> dict[tuple[str, str], str]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"策略版本哈希账本读取失败: {error}") from error
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "strategies"}
        or type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != HASH_LEDGER_SCHEMA_VERSION
    ):
        raise ValueError("策略版本哈希账本格式无效: schema_version")
    strategies = payload.get("strategies")
    if not isinstance(strategies, dict):
        raise ValueError("策略版本哈希账本格式无效: strategies")
    hashes: dict[tuple[str, str], str] = {}
    for identity, definition_hash in strategies.items():
        if not isinstance(identity, str) or _STRATEGY_IDENTITY_PATTERN.fullmatch(identity) is None:
            raise ValueError("策略版本哈希账本包含无效策略标识")
        if not isinstance(definition_hash, str) or _DEFINITION_HASH_PATTERN.fullmatch(definition_hash) is None:
            raise ValueError(f"策略版本哈希账本包含无效哈希: {identity}")
        key, version = identity.rsplit("@", 1)
        hashes[(key, version)] = definition_hash
    return hashes


def _write_hash_ledger(path: Path, hashes: Mapping[tuple[str, str], str]) -> None:
    atomic_write_json(
        path,
        {
            "schema_version": HASH_LEDGER_SCHEMA_VERSION,
            "strategies": {
                _ledger_identity(identity): definition_hash
                for identity, definition_hash in sorted(hashes.items())
            },
        },
    )


class StrategyRegistry:
    def __init__(
        self,
        directory: Path,
        *,
        ledger_path: Path | None = None,
        published_directory: Path | None = None,
    ):
        self.directory = directory.expanduser().resolve()
        self.ledger_path = ledger_path.expanduser().resolve() if ledger_path is not None else None
        self.published_directory = (
            published_directory.expanduser().resolve()
            if published_directory is not None
            else None
        )
        self._lock = RLock()
        self._state = _EMPTY_STATE
        self._observed_hashes: dict[tuple[str, str], str] = {}
        self._generation = 0
        self._loaded_at: float | None = None
        self._last_attempt_at: float | None = None
        self._last_error: str | None = None

    @property
    def state(self) -> StrategyRegistryState:
        return self._state

    @property
    def source_directories(self) -> tuple[Path, ...]:
        if self.published_directory is None:
            return (self.directory,)
        return self.directory, self.published_directory

    @property
    def status(self) -> StrategyRegistryStatus:
        with self._lock:
            return StrategyRegistryStatus(
                directory=str(self.directory),
                published_directory=(
                    str(self.published_directory)
                    if self.published_directory is not None
                    else None
                ),
                ledger_path=str(self.ledger_path) if self.ledger_path is not None else None,
                generation=self._generation,
                loaded_at=self._loaded_at,
                last_attempt_at=self._last_attempt_at,
                last_error=self._last_error,
                strategy_count=len(self._state.strategies),
                latest_versions=MappingProxyType(dict(self._state.latest_versions)),
            )

    def configure(
        self,
        directory: Path,
        *,
        ledger_path: Path | None = None,
        published_directory: Path | None = None,
    ) -> None:
        resolved = directory.expanduser().resolve()
        resolved_ledger = ledger_path.expanduser().resolve() if ledger_path is not None else None
        resolved_published = (
            published_directory.expanduser().resolve()
            if published_directory is not None
            else None
        )
        with self._lock:
            if (
                resolved == self.directory
                and resolved_ledger == self.ledger_path
                and resolved_published == self.published_directory
            ):
                return
            self.directory = resolved
            self.ledger_path = resolved_ledger
            self.published_directory = resolved_published
            self._state = _EMPTY_STATE
            self._observed_hashes = {}
            self._generation = 0
            self._loaded_at = None
            self._last_attempt_at = None
            self._last_error = None

    def record_reload_failure(self, error: Exception) -> None:
        with self._lock:
            self._last_attempt_at = time.time()
            self._last_error = str(error) or type(error).__name__

    def ensure_loaded(self) -> None:
        if self._state.strategies:
            return
        with self._lock:
            if not self._state.strategies:
                self.reload()

    def reload(self) -> StrategyRegistryState:
        with self._lock:
            self._last_attempt_at = time.time()
            try:
                loaded = load_strategy_definitions_from_directories(self.source_directories)
                compiled = [compile_strategy(item.definition, item.definition_hash) for item in loaded]
                candidate_hashes = {
                    (item.definition.key, item.definition.version): item.definition_hash
                    for item in compiled
                }
                ledger_hashes = _load_hash_ledger(self.ledger_path)
                for identity, definition_hash in ledger_hashes.items():
                    observed_hash = self._observed_hashes.get(identity)
                    if observed_hash is not None and observed_hash != definition_hash:
                        raise ValueError(f"策略版本哈希账本与进程内记录冲突: {_ledger_identity(identity)}")
                observed_hashes = {**self._observed_hashes, **ledger_hashes}
                for identity, definition_hash in candidate_hashes.items():
                    previous_hash = observed_hashes.get(identity)
                    if previous_hash is not None and previous_hash != definition_hash:
                        raise ValueError(f"策略版本内容不可变: {_ledger_identity(identity)}")

                strategies = {
                    (item.definition.key, item.definition.version): item
                    for item in compiled
                    if item.definition.enabled
                }
                if not strategies:
                    raise ValueError("策略目录中没有启用的策略")
                latest_versions: dict[str, str] = {}
                for key, version in strategies:
                    current = latest_versions.get(key)
                    if current is None or _version_key(version) > _version_key(current):
                        latest_versions[key] = version
                candidate = StrategyRegistryState(
                    strategies=MappingProxyType(strategies),
                    latest_versions=MappingProxyType(latest_versions),
                )
                merged_hashes = {**observed_hashes, **candidate_hashes}
                if self.ledger_path is not None and merged_hashes != ledger_hashes:
                    _write_hash_ledger(self.ledger_path, merged_hashes)
            except Exception as error:
                self._last_error = str(error) or type(error).__name__
                raise
            self._state = candidate
            self._observed_hashes = merged_hashes
            self._generation += 1
            self._loaded_at = time.time()
            self._last_error = None
            return candidate

    def publish_definition(self, definition: StrategyDefinition) -> Path:
        validated = StrategyDefinition.model_validate(definition)
        snapshot = build_strategy_snapshot(validated)
        if not validated.enabled:
            raise ValueError("发布策略必须启用")
        if self.published_directory is None:
            raise ValueError("量化策略发布目录未配置")
        destination = self.published_directory / f"{validated.key}-{validated.version}.yaml"
        serialized = yaml.safe_dump(
            validated.model_dump(mode="json"),
            allow_unicode=True,
            sort_keys=False,
        )
        with self._lock:
            if destination.exists():
                existing = yaml.safe_load(destination.read_text(encoding="utf-8"))
                existing_definition = StrategyDefinition.model_validate(existing)
                if canonical_definition_hash(existing_definition) == snapshot.definition_hash:
                    identity = (snapshot.key, snapshot.version)
                    active = self._state.strategies.get(identity)
                    if active is None or active.definition_hash != snapshot.definition_hash:
                        self.reload()
                        active = self._state.strategies.get(identity)
                    if active is None or active.definition_hash != snapshot.definition_hash:
                        raise ValueError(
                            f"发布文件未在策略注册表生效: {_ledger_identity(identity)}"
                        )
                    logger.info(
                        "复用已生效的量化策略发布文件: identity=%s path=%s",
                        _ledger_identity(identity),
                        destination,
                    )
                    return destination
                raise ValueError(f"发布文件已存在且内容不同: {destination.name}")
            self.validate_definition_for_publication(validated)
            atomic_write_text(destination, serialized)
            try:
                self.reload()
            except Exception:
                durable_unlink(destination)
                raise
            return destination

    def validate_definition_for_publication(
        self,
        definition: StrategyDefinition,
    ) -> StrategySnapshot:
        snapshot = build_strategy_snapshot(definition)
        identity = (snapshot.key, snapshot.version)
        with self._lock:
            ledger_hashes = _load_hash_ledger(self.ledger_path)
            previous_hash = self._observed_hashes.get(identity) or ledger_hashes.get(identity)
            if previous_hash is not None:
                raise ValueError(f"策略版本已经存在: {_ledger_identity(identity)}")
        return snapshot

    def descriptors(self) -> list[CompiledStrategy]:
        self.ensure_loaded()
        return [
            self._state.strategies[(key, version)]
            for key, version in sorted(self._state.latest_versions.items())
        ]

    def resolve(
        self,
        key: str,
        version: str | None,
        parameters: dict[str, ParameterValue],
    ) -> StrategySnapshot:
        self.ensure_loaded()
        resolved_version = version or self._state.latest_versions.get(key)
        strategy = self._state.strategies.get((key, resolved_version or ""))
        if strategy is None:
            suffix = f"@{version}" if version else ""
            raise ValueError(f"量化策略不存在或未启用: {key}{suffix}")
        return _resolve_compiled_strategy(strategy, parameters)


def _resolve_compiled_strategy(
    strategy: CompiledStrategy,
    parameters: dict[str, ParameterValue],
) -> StrategySnapshot:
    definitions = strategy.definition.parameters
    unknown = sorted(set(parameters) - set(definitions))
    if unknown:
        raise ValueError(f"策略参数不存在: {unknown[0]}")
    resolved: dict[str, ParameterValue] = {}
    for name, definition in definitions.items():
        value = parameters.get(name, definition.default)
        if not _matches(value, definition):
            raise ValueError(f"{definition.label} 类型不正确")
        if definition.minimum is not None and float(value) < definition.minimum:
            raise ValueError(f"{definition.label} 不能小于 {definition.minimum:g}")
        if definition.maximum is not None and float(value) > definition.maximum:
            raise ValueError(f"{definition.label} 不能大于 {definition.maximum:g}")
        if definition.choices and value not in definition.choices:
            raise ValueError(f"{definition.label} 不在允许选项中")
        resolved[name] = value
    for constraint in strategy.definition.constraints:
        _validate_constraint(constraint, resolved)
    for name, indicator in strategy.definition.indicators.items():
        period = _integer_argument(indicator.period, resolved) if indicator.period is not None else None
        offset = _integer_argument(indicator.offset, resolved)
        if period is not None and (period < 1 or period > MAX_INDICATOR_PERIOD):
            raise ValueError(f"指标 {name} period 必须在 1 到 {MAX_INDICATOR_PERIOD} 之间")
        if offset < 0 or offset > MAX_INDICATOR_OFFSET:
            raise ValueError(f"指标 {name} offset 必须在 0 到 {MAX_INDICATOR_OFFSET} 之间")
    return StrategySnapshot(
        key=strategy.definition.key,
        version=strategy.definition.version,
        definition_hash=strategy.definition_hash,
        parameters=resolved,
        definition=strategy.definition,
    )


def build_strategy_snapshot(
    definition: StrategyDefinition,
    parameters: dict[str, ParameterValue] | None = None,
) -> StrategySnapshot:
    compiled = compile_strategy(definition)
    return _resolve_compiled_strategy(compiled, parameters or {})


_strategy_registry = StrategyRegistry(DEFAULT_STRATEGY_DIRECTORY)


def get_strategy_registry() -> StrategyRegistry:
    return _strategy_registry


def configure_strategy_registry(
    directory: Path,
    ledger_path: Path | None = None,
    published_directory: Path | None = None,
) -> StrategyRegistryState:
    _strategy_registry.configure(
        directory,
        ledger_path=ledger_path,
        published_directory=published_directory,
    )
    return _strategy_registry.reload()
