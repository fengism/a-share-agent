from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from app.configuration.paths import DATA_DIR
from app.core.cache import cache
from app.infrastructure.persistence.ddl import (
    ANALYSIS_HISTORY_INDEXES,
    ANALYSIS_HISTORY_TABLE,
)
from app.infrastructure.persistence.history_index import HistoryIndexCoordinator
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.persistence import archive as archive_store
from app.modules.analysis.persistence import history_index as history_store
from app.modules.analysis.prompts import ANALYSIS_PROMPT_SPEC

logger = logging.getLogger(__name__)

_DATA_DIR = DATA_DIR / "analyses"
_USERS_DIR_NAME = "users"
_HISTORY_INDEX = HistoryIndexCoordinator(
    kind="analysis",
    storage_root=lambda: str(_DATA_DIR.resolve()),
    schema_ddl=(ANALYSIS_HISTORY_TABLE, *ANALYSIS_HISTORY_INDEXES),
    label="分析",
    logger=logger,
)
_INDEX_LOCK = _HISTORY_INDEX.index_lock
_INDEXED_ROOTS = _HISTORY_INDEX.indexed_roots
_SCHEMA_LOCK = _HISTORY_INDEX.schema_lock
_SCHEMA_DATABASES = _HISTORY_INDEX.schema_databases


def analysis_cache_key(user_id: int, code: str, date: str) -> str:
    """构造按用户和 Prompt 版本隔离的分析结果缓存 key。"""
    return ANALYSIS_PROMPT_SPEC.cache_key("user", user_id, code, date)


def _user_stock_dir(user_id: int, code: str) -> Path:
    return archive_store.user_stock_dir(_DATA_DIR, _USERS_DIR_NAME, user_id, code)


def _legacy_stock_dir(code: str) -> Path:
    return archive_store.legacy_stock_dir(_DATA_DIR, code)


def _load_path(filepath: Path) -> AnalysisResult | None:
    return archive_store.load_path(filepath, logger)


def _summary_from_path(filepath: Path, fallback_code: str) -> dict[str, object] | None:
    return history_store.summary_from_path(filepath, fallback_code, logger)


def _storage_root() -> str:
    return _HISTORY_INDEX.storage_root()


def _index_key() -> tuple[str, str]:
    return _HISTORY_INDEX.index_key()


def _ensure_index_schema() -> None:
    _HISTORY_INDEX.ensure_schema()


def _history_row(
    scope_user_id: int,
    filepath: Path,
    summary: dict[str, object],
) -> tuple[object, ...]:
    return history_store.history_row(_HISTORY_INDEX, scope_user_id, filepath, summary)


def _upsert_history_summary(
    scope_user_id: int,
    filepath: Path,
    summary: dict[str, object],
) -> None:
    history_store.upsert_history_row(
        _HISTORY_INDEX,
        _history_row(scope_user_id, filepath, summary),
    )


def _iter_history_files():
    return history_store.iter_history_files(_DATA_DIR, _USERS_DIR_NAME)


def _rebuild_analysis_history_index_locked() -> None:
    _ensure_index_schema()
    history_store.rebuild_history_index(
        _HISTORY_INDEX,
        _iter_history_files(),
        _summary_from_path,
        _history_row,
        logger,
    )


def _ensure_history_index() -> None:
    _HISTORY_INDEX.ensure(_rebuild_analysis_history_index_locked)


def _mark_history_index_dirty() -> None:
    _HISTORY_INDEX.mark_dirty()


def save_analysis(result: AnalysisResult, user_id: int) -> Path:
    """将分析结果原子写入当前用户的股票日期文件。"""
    filepath = _user_stock_dir(user_id, result.stock_code) / f"{result.analysis_date}.json"
    archive_store.save_result(filepath, result)
    try:
        _upsert_history_summary(user_id, filepath, archive_store.result_summary(result))
    except Exception:
        _mark_history_index_dirty()
        logger.warning("写入分析历史索引失败: %s", filepath, exc_info=True)
    logger.info("分析结果已保存: user_id=%s, path=%s", user_id, filepath)
    return filepath


def load_analysis(code: str, date: str, user_id: int) -> AnalysisResult | None:
    """优先读取用户结果，未命中时只读兼容旧全局结果。"""
    user_result = _load_path(_user_stock_dir(user_id, code) / f"{date}.json")
    if user_result is not None:
        return user_result
    return _load_path(_legacy_stock_dir(code) / f"{date}.json")


def delete_analysis(
    code: str,
    date: str,
    user_id: int,
    can_delete_legacy: bool = False,
) -> bool:
    """删除当前用户记录；管理员可在用户记录不存在时删除旧版全局记录。"""
    if len(code) != 6 or not code.isdigit() or len(date) != 8 or not date.isdigit():
        return False

    scope_user_id = user_id
    filepath = _user_stock_dir(user_id, code) / f"{date}.json"
    if not filepath.is_file():
        if not can_delete_legacy:
            return False
        scope_user_id = 0
        filepath = _legacy_stock_dir(code) / f"{date}.json"
        if not filepath.is_file():
            return False

    filepath.unlink()
    try:
        history_store.delete_history_row(_HISTORY_INDEX, scope_user_id, code, date)
    except Exception:
        _mark_history_index_dirty()
        logger.warning("删除分析历史索引失败: %s", filepath, exc_info=True)

    if scope_user_id == 0:
        cache.clear()
    else:
        cache.delete(analysis_cache_key(user_id, code, date))
    logger.info("分析历史已删除: user_id=%s, scope_user_id=%s, path=%s", user_id, scope_user_id, filepath)
    return True


def get_analysis_by_date(
    code: str,
    date: str,
    user_id: int,
    *,
    cache_ttl: int = 14400,
) -> AnalysisResult | None:
    """优先从用户缓存读取指定日期分析结果，未命中则读取文件。"""
    cache_key = analysis_cache_key(user_id, code, date)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = load_analysis(code, date, user_id)
    if result is not None:
        cache.set(cache_key, result, ttl=cache_ttl)
    return result


def get_latest_analysis(code: str, user_id: int, *, cache_ttl: int = 14400) -> AnalysisResult | None:
    """读取当前用户指定股票当天的最新分析结果。"""
    today = datetime.now().strftime("%Y%m%d")
    return get_analysis_by_date(code, today, user_id, cache_ttl=cache_ttl)


def rebuild_analysis_history_index() -> None:
    """全量重建当前分析目录的摘要索引，用于启动期兼容旧 JSON。"""
    _HISTORY_INDEX.rebuild(_rebuild_analysis_history_index_locked)


def ensure_analysis_history_index() -> None:
    """确保当前分析目录已完成旧文件索引回填。"""
    _ensure_history_index()


def _query_history(
    user_id: int,
    code: str | None,
    limit: int,
    offset: int,
    can_delete_legacy: bool,
) -> list[dict]:
    _ensure_history_index()
    return history_store.query_history(_HISTORY_INDEX, user_id, code, limit, offset, can_delete_legacy)


def list_analyses(
    code: str,
    user_id: int,
    limit: int = 100,
    offset: int = 0,
    can_delete_legacy: bool = False,
) -> list[dict]:
    """列出当前用户与旧全局记录，用户同日记录优先。"""
    return _query_history(user_id, code, limit, offset, can_delete_legacy)


def list_all_analyses(
    user_id: int,
    limit: int = 100,
    offset: int = 0,
    can_delete_legacy: bool = False,
) -> list[dict]:
    """列出当前用户全部历史，并只读兼容旧全局历史。"""
    return _query_history(user_id, None, limit, offset, can_delete_legacy)
