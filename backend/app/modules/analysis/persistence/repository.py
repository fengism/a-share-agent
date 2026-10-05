from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.configuration.paths import DATA_DIR
from app.core.cache import analysis_cache as cache
from app.core.market import is_hk_code
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
_MARKET_TIMEZONE = ZoneInfo("Asia/Shanghai")
_KEY_LEVELS_VERSION = "key-levels-v1"

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
    """构造按用户、Prompt 与关键点位算法版本隔离的分析结果缓存 key。"""
    return ANALYSIS_PROMPT_SPEC.cache_key("user", user_id, code, date, _KEY_LEVELS_VERSION)


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


def _version_path(user_id: int, code: str, date: str, report_id: str) -> Path:
    if not re.fullmatch(r"[0-9]{6}", code) or not re.fullmatch(r"[0-9]{8}", date) or not re.fullmatch(r"[a-f0-9]{32,64}", report_id):
        raise ValueError("报告版本标识无效")
    return _user_stock_dir(user_id, code) / "versions" / date / f"{report_id}.json"


def _save_version(path: Path, result: AnalysisResult) -> None:
    if path.exists():
        existing = _load_path(path)
        if existing is None or existing.model_dump() != result.model_dump():
            raise ValueError("报告版本已存在且内容不同，拒绝覆盖")
        return
    archive_store.save_result(path, result)


def save_analysis(result: AnalysisResult, user_id: int) -> Path:
    """先保存不可变版本，再更新日期别名和索引；重试保存同一版本不会重复创建。"""
    if not result.report_id:
        result.report_id = uuid4().hex
    if not result.generated_at:
        result.generated_at = datetime.now(_MARKET_TIMEZONE).isoformat()
    version = _version_path(user_id, result.stock_code, result.analysis_date, result.report_id)
    version_existed = version.exists()
    filepath = _user_stock_dir(user_id, result.stock_code) / f"{result.analysis_date}.json"
    with _HISTORY_INDEX.mutation() as mutation:
        previous = _load_path(filepath)
        if filepath.exists() and previous is None:
            raise ValueError("已有日期报告无法读取，拒绝覆盖")
        if previous is not None:
            if not previous.report_id:
                previous.report_id = hashlib.sha256(filepath.read_bytes()).hexdigest()
            _save_version(_version_path(user_id, previous.stock_code, previous.analysis_date, previous.report_id), previous)
        _save_version(version, result)
        try:
            archive_store.save_result(filepath, result)
            _upsert_history_summary(user_id, filepath, archive_store.result_summary(result))
        except Exception:
            # 首次写入失败时不留下孤立版本；已存在版本属于同一报告的幂等保存，不能删除。
            if not version_existed:
                version.unlink(missing_ok=True)
            if previous is not None:
                archive_store.save_result(filepath, previous)
            else:
                filepath.unlink(missing_ok=True)
            raise
        mutation.complete()
    logger.info("分析结果已保存: user_id=%s, path=%s, report_id=%s", user_id, filepath, result.report_id)
    return filepath


def list_analysis_versions(code: str, date: str, user_id: int, *, limit: int = 50, offset: int = 0) -> list[dict]:
    directory = _version_path(user_id, code, date, "0" * 32).parent
    versions = []
    for path in directory.glob("*.json"):
        result = _load_path(path)
        if result is not None:
            versions.append({**archive_store.result_summary(result), "report_id": result.report_id,
                             "generated_at": result.generated_at})
    versions.sort(key=lambda item: (item["generated_at"] or "", item["report_id"] or ""), reverse=True)
    return versions[offset:offset + limit]


def load_analysis_version(code: str, date: str, report_id: str, user_id: int) -> AnalysisResult | None:
    return _load_path(_version_path(user_id, code, date, report_id))


def load_analysis(code: str, date: str, user_id: int) -> AnalysisResult | None:
    """优先读取用户结果，未命中时只读兼容旧全局结果。"""
    return _load_scoped_analysis(code, date, user_id)[0]


def _load_scoped_analysis(code: str, date: str, user_id: int) -> tuple[AnalysisResult | None, bool]:
    """读取分析结果，并返回是否来自当前用户自己的记录。

    第二个返回值为 ``False`` 表示命中的是 legacy 全局记录。这类记录属于所有用户可见，
    绝不能写进某个用户的缓存命名空间：``delete_analysis`` 只失效删除者与 scope 两个 key，
    管理员删掉 legacy 记录后，其他用户此前缓存过的那份不会被清掉，能多读最长 4 小时。
    """
    user_result = _load_path(_user_stock_dir(user_id, code) / f"{date}.json")
    if user_result is not None:
        return user_result, True
    return _load_path(_legacy_stock_dir(code) / f"{date}.json"), False


def delete_analysis(
    code: str,
    date: str,
    user_id: int,
    can_delete_legacy: bool = False,
) -> bool:
    """删除当前用户记录；管理员可在用户记录不存在时删除旧版全局记录。"""
    if not code.isdigit() or len(date) != 8 or not date.isdigit():
        return False
    # 港股为 1-5 位代码，A 股为 6 位；此前只放行 6 位，导致港股分析记录无法删除。
    if len(code) != 6 and not is_hk_code(code):
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

    with _HISTORY_INDEX.mutation() as mutation:
        if scope_user_id != 0:
            version_dir = _version_path(user_id, code, date, "0" * 32).parent
            for version_file in version_dir.glob("*.json"):
                version_file.unlink()
        filepath.unlink()
        try:
            history_store.delete_history_row(_HISTORY_INDEX, scope_user_id, code, date)
        except Exception:
            logger.warning("删除分析历史索引失败: %s", filepath, exc_info=True)
        else:
            mutation.complete()

    cache.delete_many(
        {
            analysis_cache_key(user_id, code, date),
            analysis_cache_key(scope_user_id, code, date),
        }
    )
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

    result, is_user_scoped = _load_scoped_analysis(code, date, user_id)
    # 只缓存用户自己的记录；legacy 全局记录每次回源读文件，
    # 这样管理员删除后立即失效，不会有任何用户继续命中缓存副本。
    if result is not None and is_user_scoped:
        cache.set(cache_key, result, ttl=cache_ttl)
    return result


def get_latest_analysis(code: str, user_id: int, *, cache_ttl: int = 14400) -> AnalysisResult | None:
    """读取当前用户可见的指定股票最新分析结果。"""
    today = datetime.now(_MARKET_TIMEZONE).strftime("%Y%m%d")
    today_result = get_analysis_by_date(code, today, user_id, cache_ttl=cache_ttl)
    if today_result is not None:
        return today_result
    latest = _query_history(user_id, code, 1, 0, False)
    if not latest:
        return None
    return get_analysis_by_date(code, str(latest[0]["analysis_date"]), user_id, cache_ttl=cache_ttl)


def rebuild_analysis_history_index() -> None:
    """全量重建当前分析目录的摘要索引，用于启动期兼容旧 JSON。"""
    _HISTORY_INDEX.rebuild(_rebuild_analysis_history_index_locked)


def ensure_analysis_history_index() -> None:
    """确保当前分析目录已完成旧文件索引回填。"""
    _ensure_history_index()


def analysis_history_index_snapshot() -> dict[str, object]:
    """返回有界的分析历史索引恢复状态。"""
    return _HISTORY_INDEX.snapshot()


def _query_history(
    user_id: int,
    code: str | None,
    limit: int,
    offset: int,
    can_delete_legacy: bool,
    query: str | None = None,
) -> list[dict]:
    _ensure_history_index()
    return history_store.query_history(
        _HISTORY_INDEX,
        user_id,
        code,
        limit,
        offset,
        can_delete_legacy,
        query,
    )


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
    query: str | None = None,
) -> list[dict]:
    """列出当前用户全部历史，并只读兼容旧全局历史。"""
    return _query_history(user_id, None, limit, offset, can_delete_legacy, query)
