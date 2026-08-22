import logging
from pathlib import Path

from app.configuration.paths import DATA_DIR
from app.infrastructure.persistence.ddl import (
    INDUSTRY_CHAIN_HISTORY_INDEXES,
    INDUSTRY_CHAIN_HISTORY_TABLE,
)
from app.infrastructure.persistence.history_index import HistoryIndexCoordinator
from app.modules.industry_chain.models import IndustryChainResult
from app.modules.industry_chain.persistence import archive as archive_store
from app.modules.industry_chain.persistence import history_index as history_store
from app.modules.industry_chain.schemas import IndustryChainHistoryItem

_DATA_DIR = DATA_DIR / "industry_chains"
logger = logging.getLogger(__name__)
_HISTORY_INDEX = HistoryIndexCoordinator(
    kind="industry_chain",
    storage_root=lambda: str(_DATA_DIR.resolve()),
    schema_ddl=(INDUSTRY_CHAIN_HISTORY_TABLE, *INDUSTRY_CHAIN_HISTORY_INDEXES),
    label="产业链",
    logger=logger,
)
_INDEX_LOCK = _HISTORY_INDEX.index_lock
_INDEXED_ROOTS = _HISTORY_INDEX.indexed_roots
_SCHEMA_LOCK = _HISTORY_INDEX.schema_lock
_SCHEMA_DATABASES = _HISTORY_INDEX.schema_databases


def _safe_name(name: str) -> str:
    return archive_store.safe_name(name)


def _archive_id(timestamp: str | None = None) -> str:
    return archive_store.archive_id(timestamp)


def _history_item_from_payload(payload: dict, root: Path, fallback_archive_id: str) -> IndustryChainHistoryItem:
    return history_store.history_item_from_payload(payload, root, fallback_archive_id)


def _load_history_item(path: Path, root: Path) -> IndustryChainHistoryItem | None:
    return history_store.load_history_item(path, root, logger)


def _storage_root() -> str:
    return _HISTORY_INDEX.storage_root()


def _index_key() -> tuple[str, str]:
    return _HISTORY_INDEX.index_key()


def _ensure_index_schema() -> None:
    _HISTORY_INDEX.ensure_schema()


def _history_row(
    scope_user_id: int,
    safe_name: str,
    path: Path,
    item: IndustryChainHistoryItem,
) -> tuple[object, ...]:
    return history_store.history_row(_HISTORY_INDEX, scope_user_id, safe_name, path, item)


def _upsert_history_item(
    scope_user_id: int,
    safe_name: str,
    path: Path,
    item: IndustryChainHistoryItem,
) -> None:
    history_store.upsert_history_item(_HISTORY_INDEX, scope_user_id, safe_name, path, item)


def _iter_history_files():
    return history_store.iter_history_files(_DATA_DIR, _safe_name)


def _ensure_history_index() -> None:
    history_store.ensure_history_index(
        _HISTORY_INDEX,
        _DATA_DIR,
        _safe_name,
        _load_history_item,
        logger,
    )


def save_industry_chain(
    name: str,
    result: IndustryChainResult,
    user_id: int,
    archive_id: str | None = None,
) -> str:
    """将产业链分析结果以 JSON 格式原子写入当前用户存档。"""
    resolved_archive_id = _archive_id(archive_id)
    result.archive_id = resolved_archive_id
    result.archive_status = "saved"
    with _HISTORY_INDEX.mutation() as mutation:
        path, payload = archive_store.save_archive(
            _DATA_DIR,
            name,
            result,
            user_id,
            resolved_archive_id,
            _safe_name,
        )
        try:
            _upsert_history_item(
                user_id,
                _safe_name(name),
                path,
                _history_item_from_payload(payload, path.parent, resolved_archive_id),
            )
        except Exception:
            logger.warning("写入产业链历史索引失败: %s", path, exc_info=True)
        else:
            mutation.complete()
    return resolved_archive_id


def load_industry_chain(name: str, archive_id: str, user_id: int) -> IndustryChainResult | None:
    """优先加载当前用户存档，并只读兼容旧版全局存档。"""
    return archive_store.load_archive(_DATA_DIR, name, archive_id, user_id, _safe_name)


def delete_industry_chain(
    name: str,
    archive_id: str,
    user_id: int,
    can_delete_legacy: bool = False,
) -> bool:
    """删除当前用户存档；管理员可在用户存档不存在时删除旧版全局存档。"""
    if not name.strip() or not archive_id or "/" in archive_id or "\\" in archive_id:
        return False

    safe_name = _safe_name(name)
    scope_user_id = user_id
    path = archive_store.user_archive_path(_DATA_DIR, name, archive_id, user_id, _safe_name)
    if not path.is_file():
        if not can_delete_legacy:
            return False
        scope_user_id = 0
        path = archive_store.legacy_archive_path(_DATA_DIR, name, archive_id, _safe_name)
        if not path.is_file():
            return False

    with _HISTORY_INDEX.mutation() as mutation:
        path.unlink()
        try:
            history_store.delete_history_item(_HISTORY_INDEX, scope_user_id, safe_name, archive_id)
        except Exception:
            logger.warning("删除产业链历史索引失败: %s", path, exc_info=True)
        else:
            mutation.complete()
    logger.info("产业链存档已删除: user_id=%s, scope_user_id=%s, path=%s", user_id, scope_user_id, path)
    return True


def rebuild_industry_chain_history_index() -> None:
    """全量重建当前产业链目录的摘要索引，用于启动期兼容旧 JSON。"""
    history_store.rebuild_history_index(
        _HISTORY_INDEX,
        _DATA_DIR,
        _safe_name,
        _load_history_item,
        logger,
    )


def ensure_industry_chain_history_index() -> None:
    """确保当前产业链目录已完成旧文件索引回填。"""
    _ensure_history_index()


def industry_chain_history_index_snapshot() -> dict[str, object]:
    """返回有界的产业链历史索引恢复状态。"""
    return _HISTORY_INDEX.snapshot()


def list_industry_chains(
    user_id: int,
    name: str | None = None,
    limit: int = 100,
    offset: int = 0,
    can_delete_legacy: bool = False,
) -> list[IndustryChainHistoryItem]:
    """列出当前用户与旧版全局产业链摘要，用户同名存档优先。"""
    return history_store.list_history(
        _HISTORY_INDEX,
        _DATA_DIR,
        _safe_name,
        _load_history_item,
        logger,
        user_id,
        name,
        limit,
        offset,
        can_delete_legacy,
    )


__all__ = [
    "save_industry_chain",
    "load_industry_chain",
    "delete_industry_chain",
    "list_industry_chains",
    "ensure_industry_chain_history_index",
    "industry_chain_history_index_snapshot",
    "rebuild_industry_chain_history_index",
]
