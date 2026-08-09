import json
import logging
from pathlib import Path

from app.infrastructure.persistence.json_storage import atomic_write_text
from app.modules.analysis.models import AnalysisResult


def user_stock_dir(data_dir: Path, users_dir_name: str, user_id: int, code: str) -> Path:
    return data_dir / users_dir_name / str(user_id) / code


def legacy_stock_dir(data_dir: Path, code: str) -> Path:
    return data_dir / code


def load_path(filepath: Path, logger: logging.Logger) -> AnalysisResult | None:
    if not filepath.exists():
        return None
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return AnalysisResult.model_validate(data)
    except Exception as exc:
        logger.warning("加载分析结果失败: %s, error=%s", filepath, exc)
        return None


def save_result(filepath: Path, result: AnalysisResult) -> None:
    atomic_write_text(filepath, result.model_dump_json(indent=2, ensure_ascii=False))


def result_summary(result: AnalysisResult) -> dict[str, object]:
    return {
        "stock_code": result.stock_code,
        "stock_name": result.stock_name,
        "analysis_date": result.analysis_date,
        "current_price": result.current_price,
        "overall_rating": result.overall_rating,
        "signal": result.signal,
        "confidence": result.confidence,
    }
