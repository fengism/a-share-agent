"""按日期存取潜力股挖掘结果（JSON 文件，原子写）。"""

from __future__ import annotations

from pathlib import Path

from app.configuration.paths import DATA_DIR
from app.infrastructure.persistence.json_storage import atomic_write_text
from app.modules.potential.schemas import PotentialDailyResult

_DATA_DIR = DATA_DIR / "potential_stocks"


def _result_path(date: str) -> Path:
    return _DATA_DIR / f"{date}.json"


def save_potential_result(result: PotentialDailyResult) -> None:
    """将挖掘结果按日期原子写入本地文件。"""
    atomic_write_text(_result_path(result.date), result.model_dump_json(indent=2))


def load_potential_result(date: str) -> PotentialDailyResult | None:
    """加载指定日期的挖掘结果，文件不存在时返回 None。"""
    path = _result_path(date)
    if not path.exists():
        return None
    return PotentialDailyResult.model_validate_json(path.read_text(encoding="utf-8"))


def list_potential_dates(limit: int = 30) -> list[str]:
    """按日期倒序列出已有结果的日期（最多 limit 个）。"""
    if not _DATA_DIR.exists():
        return []
    dates = sorted(
        (path.stem for path in _DATA_DIR.glob("*.json") if path.stem.count("-") == 2),
        reverse=True,
    )
    return dates[:limit]


def list_potential_summaries(limit: int = 30) -> list[tuple[str, int]]:
    """按日期倒序列出 (日期, 命中数量)。"""
    return [
        (date, len(load_potential_result(date).items) if load_potential_result(date) else 0)
        for date in list_potential_dates(limit)
    ]


def has_potential_result(date: str) -> bool:
    return _result_path(date).exists()
