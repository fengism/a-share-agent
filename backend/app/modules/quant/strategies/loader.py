"""安全加载并规范化 YAML 策略定义。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from app.modules.quant.strategies.contracts import StrategyDefinition

MAX_STRATEGY_FILES = 100
MAX_STRATEGY_FILE_BYTES = 1_000_000


@dataclass(frozen=True, slots=True)
class LoadedStrategyDefinition:
    source: Path
    definition: StrategyDefinition
    definition_hash: str


_OPTIONAL_INDICATOR_FIELDS_ADDED_IN_V1 = (
    "volume_input",
    "left",
    "right",
    "zero_value",
)


def _canonical_definition_payload(definition: StrategyDefinition) -> dict[str, Any]:
    payload = definition.model_dump(mode="json")
    for indicator in payload.get("indicators", {}).values():
        for field in _OPTIONAL_INDICATOR_FIELDS_ADDED_IN_V1:
            if indicator.get(field) is None:
                indicator.pop(field, None)
    if "position" in payload and payload["position"].get("target_weight") is None:
        payload["position"].pop("target_weight", None)
    return cast(dict[str, Any], payload)


def canonical_definition_hash(definition: StrategyDefinition) -> str:
    payload = json.dumps(
        _canonical_definition_payload(definition),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def load_strategy_definitions(directory: Path) -> list[LoadedStrategyDefinition]:
    return load_strategy_definitions_from_directories((directory,))


def load_strategy_definitions_from_directories(
    directories: Sequence[Path],
) -> list[LoadedStrategyDefinition]:
    if not directories:
        raise ValueError("策略目录不能为空")
    paths: list[Path] = []
    for index, directory in enumerate(directories):
        if not directory.is_dir():
            if index == 0:
                raise ValueError(f"策略目录不存在: {directory}")
            continue
        paths.extend(sorted((*directory.glob("*.yaml"), *directory.glob("*.yml"))))
    if not paths:
        raise ValueError(f"策略目录没有 YAML 定义: {directories[0]}")
    if len(paths) > MAX_STRATEGY_FILES:
        raise ValueError(f"策略文件数量超过限制: {len(paths)} > {MAX_STRATEGY_FILES}")

    loaded: list[LoadedStrategyDefinition] = []
    versions: set[tuple[str, str]] = set()
    for path in paths:
        if path.stat().st_size > MAX_STRATEGY_FILE_BYTES:
            raise ValueError(f"策略文件超过大小限制: {path.name}")
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as error:
            raise ValueError(f"策略文件加载失败 {path.name}: {error}") from error
        if not isinstance(raw, dict):
            raise ValueError(f"策略文件根节点必须是对象: {path.name}")
        try:
            definition = StrategyDefinition.model_validate(raw)
        except ValidationError as error:
            raise ValueError(f"策略文件校验失败 {path.name}: {error}") from error
        identity = (definition.key, definition.version)
        if identity in versions:
            raise ValueError(f"重复策略版本: {definition.key}@{definition.version}")
        versions.add(identity)
        loaded.append(
            LoadedStrategyDefinition(
                source=path,
                definition=definition,
                definition_hash=canonical_definition_hash(definition),
            )
        )
    return loaded
