"""轮询策略目录指纹并触发原子全量重载。"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Sequence
from pathlib import Path

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.modules.quant.strategies.registry import StrategyRegistry

logger = logging.getLogger(__name__)


def strategy_directory_fingerprint(directory: Path) -> str:
    return strategy_directories_fingerprint((directory,))


def strategy_directories_fingerprint(directories: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for directory in directories:
        digest.update(str(directory).encode("utf-8"))
        digest.update(str(directory.is_dir()).encode("ascii"))
        if not directory.is_dir():
            continue
        for path in sorted((*directory.glob("*.yaml"), *directory.glob("*.yml"))):
            stat = path.stat()
            digest.update(path.name.encode("utf-8"))
            digest.update(str(stat.st_size).encode("ascii"))
            digest.update(str(stat.st_mtime_ns).encode("ascii"))
    return digest.hexdigest()


class StrategyDirectoryWatcher:
    def __init__(self, registry: StrategyRegistry, interval_seconds: float):
        self.registry = registry
        self.interval_seconds = interval_seconds
        self._fingerprint = strategy_directories_fingerprint(registry.source_directories)

    async def reload_if_changed(self) -> bool:
        try:
            fingerprint = strategy_directories_fingerprint(self.registry.source_directories)
            if fingerprint == self._fingerprint:
                return False
            state = await call_blocking(self.registry.reload, semaphore=misc_semaphore)
        except Exception as error:
            # 指纹仅在重载成功后更新：半写的 YAML 导致失败时，
            # 下次轮询仍会检测到变化并重试
            self.registry.record_reload_failure(error)
            logger.warning("量化策略热加载失败，继续使用上一版本", exc_info=True)
            return False
        self._fingerprint = fingerprint
        logger.info(
            "量化策略热加载完成: strategies=%s",
            len(state.strategies),
        )
        return True

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.interval_seconds)
            await self.reload_if_changed()
