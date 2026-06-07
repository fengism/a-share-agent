import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from app.models.industry_chain import IndustryChainHistoryItem, IndustryChainResult

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "industry_chains"


def _safe_name(name: str) -> str:
    """根据产业链名称生成目录安全的子目录名。

    Param:
        name: 产业链原始名称
    Return:
        str: URL 编码后的安全目录名
    """
    return quote(name.strip(), safe="")


def _archive_id(timestamp: str | None = None) -> str:
    """生成存档 ID (YYYYMMDD_HHMMSS)。

    Param:
        timestamp: 可选 ISO 字符串；为空则使用当前本地时间
    Return:
        str: 时间戳形式的存档 ID
    """
    if timestamp:
        return timestamp
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _archive_path(name: str, archive_id: str) -> Path:
    """根据名称与存档 ID 生成文件路径。

    Param:
        name: 产业链名称
        archive_id: 存档 ID (YYYYMMDD_HHMMSS)
    Return:
        Path: 存档文件路径
    """
    return _DATA_DIR / _safe_name(name) / f"{archive_id}.json"


def save_industry_chain(name: str, result: IndustryChainResult, archive_id: str | None = None) -> str:
    """将产业链分析结果以 JSON 格式原子写入本地存档。

    Param:
        name: 产业链名称
        result: 产业链分析结果
        archive_id: 可选存档 ID，默认当前时间
    Return:
        str: 实际使用的存档 ID
    """
    archive_id = _archive_id(archive_id)
    target_dir = _DATA_DIR / _safe_name(name)
    target_dir.mkdir(parents=True, exist_ok=True)

    result.name = name
    payload = {
        "archive_id": archive_id,
        "name": name,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "result": result.model_dump(),
    }

    path = target_dir / f"{archive_id}.json"
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
    return archive_id


def load_industry_chain(name: str, archive_id: str) -> IndustryChainResult | None:
    """按名称与存档 ID 加载产业链分析结果。

    Param:
        name: 产业链名称
        archive_id: 存档 ID
    Return:
        IndustryChainResult 或 None（文件不存在或解析失败）
    """
    path = _archive_path(name, archive_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return IndustryChainResult.model_validate(payload.get("result", {}))
    except (json.JSONDecodeError, ValueError):
        return None


def list_industry_chains(name: str | None = None) -> list[IndustryChainHistoryItem]:
    """列出已存档的产业链分析摘要，按时间倒序。

    Param:
        name: 可选名称过滤；为空则列出全部
    Return:
        历史摘要列表
    """
    if not _DATA_DIR.exists():
        return []

    items: list[IndustryChainHistoryItem] = []
    name_filter = _safe_name(name) if name else None

    if name_filter:
        roots = [_DATA_DIR / name_filter]
    else:
        roots = sorted([d for d in _DATA_DIR.iterdir() if d.is_dir()], reverse=True)

    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.glob("*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                continue
            archive_id = path.stem
            original_name = payload.get("name") or root.name
            saved_at = payload.get("saved_at", "")
            result_data = payload.get("result", {})
            summary = result_data.get("summary") or result_data.get("llm_review", "")[:80]
            items.append(
                IndustryChainHistoryItem(
                    name=original_name,
                    archive_id=archive_id,
                    saved_at=saved_at,
                    title=f"{original_name} 产业链分析",
                    summary=summary.strip(),
                )
            )
    return items


__all__ = ["save_industry_chain", "load_industry_chain", "list_industry_chains"]
