"""文件型快照目录的保留清理。

SQLite 行级保留在 ``retention.py``；本模块负责按 mtime 清理 JSON/导出等
按日累积的文件，避免 ``data/**`` 目录无限增长。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def purge_old_files(
    directory: Path,
    *,
    keep_days: int,
    now: float | None = None,
    pattern: str = "*.json",
) -> int:
    """删除目录下超过保留期的文件，返回删除数量。

    Param:
        directory: 目标目录；不存在时返回 0
        keep_days: 保留天数，<=0 时跳过（避免误删全部）
        now: 当前时间戳，便于测试注入
        pattern: 文件匹配模式
    Return:
        删除的文件数量
    """
    if keep_days <= 0 or not directory.is_dir():
        return 0
    current = time.time() if now is None else now
    cutoff = current - keep_days * 24 * 60 * 60
    deleted = 0
    for path in directory.glob(pattern):
        try:
            if not path.is_file():
                continue
            if path.stat().st_mtime >= cutoff:
                continue
            path.unlink()
            deleted += 1
        except OSError as error:
            logger.warning("淘汰过期快照文件失败 path=%s error_type=%s", path, type(error).__name__)
    if deleted:
        logger.info("淘汰过期快照文件完成 dir=%s deleted=%s keep_days=%s", directory, deleted, keep_days)
    return deleted
