"""产业链知识库 YAML 定义加载器。

内置定义目录 + 外部导入目录双源合并，目录指纹变化时自动原子重载
（懒加载 + 节流）；全部文件校验通过才替换注册表，策略与
quant/strategies 的 watcher 模式保持一致。导入的链条由
import_atlas_chains() 校验后写入导入目录。
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.configuration import get_settings
from app.modules.industry_chain.atlas.contracts import (
    AtlasCatalog,
    AtlasChain,
    AtlasChainSummary,
)

logger = logging.getLogger(__name__)

DEFINITIONS_DIR = Path(__file__).parent / "definitions"
_RELOAD_THROTTLE_SECONDS = 2.0


class AtlasImportError(ValueError):
    """外部导入内容校验或冲突失败，message 面向用户。"""


@dataclass(frozen=True)
class _AtlasState:
    fingerprint: str
    chains: dict[str, AtlasChain]
    imported_slugs: frozenset[str]


def _import_dir() -> Path:
    return get_settings().industry_atlas_import_dir


def _legacy_import_dir() -> Path:
    return _import_dir().parent / "industry_chains"


def _migrate_legacy_import_dir() -> None:
    """旧版本把导入/挖掘的链条直接放在存档根目录（data/industry_chains）下，
    与用户存档目录树混居；首次加载时把根目录下的 YAML 文件一次性搬到独立导入目录。"""
    legacy = _legacy_import_dir()
    import_dir = _import_dir()
    if legacy == import_dir or not legacy.is_dir():
        return
    files = _yaml_files(legacy)
    if not files:
        return
    import_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for path in files:
        target = import_dir / path.name
        if target.exists():
            continue
        path.rename(target)
        moved += 1
    if moved:
        logger.info("产业链导入目录迁移完成: %s 个文件 -> %s", moved, import_dir)


def _yaml_files(directory: Path) -> list[Path]:
    """仅返回目录下的 YAML 文件；跳过同名子目录（存档目录可能与本目录树混居）。"""
    if not directory.is_dir():
        return []
    return [path for path in sorted((*directory.glob("*.yaml"), *directory.glob("*.yml"))) if path.is_file()]


def _directory_fingerprint(directories: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for directory in directories:
        digest.update(str(directory).encode("utf-8"))
        digest.update(str(directory.is_dir()).encode("ascii"))
        if not directory.is_dir():
            continue
        for path in _yaml_files(directory):
            try:
                stat = path.stat()
            except OSError:
                # 文件在 glob 与 stat 之间被删除（如并发导入删除），跳过本轮指纹
                continue
            digest.update(path.name.encode("utf-8"))
            digest.update(str(stat.st_size).encode("ascii"))
            digest.update(str(stat.st_mtime_ns).encode("ascii"))
    return digest.hexdigest()


def _load_directory(
    directory: Path,
    errors: list[str],
    *,
    strict: bool,
) -> dict[str, AtlasChain]:
    """加载目录下全部链条。

    strict=True（内置定义，版本受控）：任何文件解析失败都记入 errors 使整次重载失败；
    strict=False（导入/挖掘目录，外部内容）：坏文件记 warning 后跳过，
    不允许单个损坏文件冻结整个知识库的重载。
    """
    chains: dict[str, AtlasChain] = {}
    for path in _yaml_files(directory):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            chain = AtlasChain.model_validate(raw)
        except Exception as exc:
            message = f"{path.name}: {exc}"
            if strict:
                errors.append(message)
            else:
                logger.warning("产业链导入文件无效，已跳过: %s", message)
            continue
        if chain.slug in chains:
            message = f"{path.name}: slug 重复 {chain.slug!r}"
            if strict:
                errors.append(message)
            else:
                logger.warning("产业链导入文件 slug 重复，已跳过: %s", message)
            continue
        chains[chain.slug] = chain
    return chains


def _load_definitions(
    builtin_dir: Path, import_dir: Path,
) -> tuple[dict[str, AtlasChain], frozenset[str]]:
    errors: list[str] = []
    builtin = _load_directory(builtin_dir, errors, strict=True)
    imported = _load_directory(import_dir, errors, strict=False)
    if errors:
        raise ValueError("产业链定义校验失败:\n" + "\n".join(errors))
    if not builtin and not imported:
        raise ValueError("产业链定义目录为空")
    # 导入目录同 slug 覆盖内置定义；mined=True 标记为 AI 挖掘来源
    chains = {**builtin, **{slug: chain for slug, chain in imported.items()}}
    for slug in imported:
        chain = chains[slug]
        source = "mined" if chain.mined else "imported"
        chains[slug] = chain.model_copy(update={"source": source})
    return chains, frozenset(imported)


class _AtlasRegistry:
    def __init__(self) -> None:
        self.state = _AtlasState(fingerprint="", chains={}, imported_slugs=frozenset())
        self.checked_at = 0.0
        self.lock = threading.Lock()
        self._migrated = False

    def _migrate_once(self) -> None:
        if self._migrated:
            return
        try:
            _migrate_legacy_import_dir()
        except Exception:
            logger.exception("产业链导入目录迁移失败，继续使用原目录")
        finally:
            self._migrated = True

    def current(self) -> _AtlasState:
        now = time.monotonic()
        if now - self.checked_at < _RELOAD_THROTTLE_SECONDS:
            return self.state
        with self.lock:
            now = time.monotonic()
            if now - self.checked_at < _RELOAD_THROTTLE_SECONDS:
                return self.state
            self.checked_at = now
            self._migrate_once()
            fingerprint = _directory_fingerprint((DEFINITIONS_DIR, _import_dir()))
            if fingerprint != self.state.fingerprint:
                try:
                    chains, imported = _load_definitions(DEFINITIONS_DIR, _import_dir())
                except Exception:
                    logger.exception("产业链知识库重载失败，继续使用上一份有效版本")
                    return self.state
                self.state = _AtlasState(
                    fingerprint=fingerprint,
                    chains=chains,
                    imported_slugs=imported,
                )
                logger.info(
                    "产业链知识库重载完成: chains=%s (imported=%s)",
                    len(chains), len(imported),
                )
            return self.state

    def force_refresh(self) -> None:
        """导入/删除文件后立即失效节流，让下一次读取重新加载。"""
        with self.lock:
            self.checked_at = 0.0


_registry = _AtlasRegistry()


def _ensure_loaded() -> None:
    _registry.current()


def get_atlas_chain(slug: str) -> AtlasChain | None:
    return _registry.current().chains.get(slug)


def list_atlas_chains() -> list[AtlasChain]:
    chains = _registry.current().chains
    return sorted(chains.values(), key=lambda chain: chain.name)


def build_atlas_catalog() -> AtlasCatalog:
    chains = list_atlas_chains()
    unique_codes = {
        company.code
        for chain in chains
        for layer in chain.layers
        for segment in layer.segments
        for company in segment.companies
    }
    return AtlasCatalog(
        categories=list(dict.fromkeys(chain.category for chain in chains)),
        chains=[
            AtlasChainSummary(
                slug=chain.slug,
                name=chain.name,
                category=chain.category,
                summary=chain.summary,
                aliases=chain.aliases,
                tags=chain.tags,
                segment_count=chain.segment_count,
                company_count=chain.company_count,
                source=chain.source,
            )
            for chain in chains
        ],
        total_chains=len(chains),
        total_companies=len(unique_codes),
    )


# ── 外部导入 ──────────────────────────────────────────────────────────────


def _parse_import_payload(content: str) -> list[AtlasChain]:
    """支持单条对象、对象列表，或 {chains: [...]} 包装的批量结构。"""
    try:
        raw: Any = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise AtlasImportError(f"YAML/JSON 解析失败: {exc}") from exc
    if isinstance(raw, dict) and isinstance(raw.get("chains"), list):
        items = raw["chains"]
    elif isinstance(raw, dict):
        items = [raw]
    elif isinstance(raw, list):
        items = raw
    else:
        raise AtlasImportError("内容必须是链条对象、链条数组或 {chains: [...]} 结构")

    errors: list[str] = []
    chains: list[AtlasChain] = []
    seen: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"第 {index} 条: 不是对象结构")
            continue
        try:
            chain = AtlasChain.model_validate({**item, "source": "imported"})
        except Exception as exc:
            errors.append(f"第 {index} 条: {exc}")
            continue
        if chain.slug in seen:
            errors.append(f"第 {index} 条: slug 在本次导入中重复 {chain.slug!r}")
            continue
        seen.add(chain.slug)
        chains.append(chain)
    if errors:
        raise AtlasImportError("导入内容校验失败:\n" + "\n".join(errors))
    if not chains:
        raise AtlasImportError("导入内容为空")
    return chains


def import_atlas_chains(content: str, *, overwrite: bool) -> list[AtlasChain]:
    """校验并把外部链条写入导入目录；冲突（slug 已存在）时按 overwrite 决定。"""
    _ensure_loaded()
    chains = _parse_import_payload(content)
    existing = _registry.current().chains
    conflicts = sorted(chain.slug for chain in chains if chain.slug in existing)
    if conflicts and not overwrite:
        raise AtlasImportError(
            "以下产业链已存在，需 overwrite=true 才能覆盖: " + ", ".join(conflicts),
        )

    import_dir = _import_dir()
    import_dir.mkdir(parents=True, exist_ok=True)
    for chain in chains:
        _write_chain_file(import_dir, chain)
        logger.info("产业链知识库导入: %s", chain.slug)
    _registry.force_refresh()
    state = _registry.current()
    return [state.chains[chain.slug] for chain in chains if chain.slug in state.chains]


def _write_chain_file(import_dir: Path, chain: AtlasChain) -> Path:
    payload = chain.model_dump(exclude={"source"})
    target = import_dir / f"{chain.slug}.yaml"
    target.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return target


def delete_imported_chain(slug: str) -> bool:
    """删除一条外部导入的链条；内置链条不可删。返回是否存在该导入文件。"""
    _ensure_loaded()
    if slug not in _registry.current().imported_slugs:
        return False
    import_dir = _import_dir()
    for suffix in (".yaml", ".yml"):
        target = import_dir / f"{slug}{suffix}"
        if target.is_file():
            target.unlink()
            logger.info("产业链知识库删除导入链条: %s", slug)
    _registry.force_refresh()
    return True


def list_atlas_chains_imported() -> list[AtlasChain]:
    return [chain for chain in list_atlas_chains() if chain.source == "imported"]
