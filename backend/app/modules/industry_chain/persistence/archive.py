"""产业链存档文件读写。"""

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from app.infrastructure.persistence.json_storage import atomic_write_json
from app.modules.industry_chain.models import IndustryChainResult

SafeNameFunc = Callable[[str], str]


def safe_name(name: str) -> str:
    return quote(name.strip(), safe="")


def archive_id(timestamp: str | None = None) -> str:
    if timestamp:
        return timestamp
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def legacy_archive_path(
    data_dir: Path,
    name: str,
    archive_id: str,
    safe_name_func: SafeNameFunc,
) -> Path:
    return data_dir / safe_name_func(name) / f"{archive_id}.json"


def user_archive_path(
    data_dir: Path,
    name: str,
    archive_id: str,
    user_id: int,
    safe_name_func: SafeNameFunc,
) -> Path:
    return data_dir / "users" / str(user_id) / safe_name_func(name) / f"{archive_id}.json"


def build_archive_payload(
    name: str,
    result: IndustryChainResult,
    archive_id: str,
) -> dict[str, object]:
    result.name = name
    return {
        "archive_id": archive_id,
        "name": name,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "result": result.model_dump(),
    }


def save_archive(
    data_dir: Path,
    name: str,
    result: IndustryChainResult,
    user_id: int,
    archive_id: str,
    safe_name_func: SafeNameFunc,
) -> tuple[Path, dict[str, object]]:
    path = user_archive_path(data_dir, name, archive_id, user_id, safe_name_func)
    payload = build_archive_payload(name, result, archive_id)
    atomic_write_json(path, payload)
    return path, payload


def load_archive(
    data_dir: Path,
    name: str,
    archive_id: str,
    user_id: int,
    safe_name_func: SafeNameFunc,
) -> IndustryChainResult | None:
    paths = (
        user_archive_path(data_dir, name, archive_id, user_id, safe_name_func),
        legacy_archive_path(data_dir, name, archive_id, safe_name_func),
    )
    for path in paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return IndustryChainResult.model_validate(payload.get("result", {}))
        except (json.JSONDecodeError, ValueError):
            return None
    return None
