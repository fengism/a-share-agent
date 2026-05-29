from __future__ import annotations

import json
import logging
from pathlib import Path

from app.models.analysis import AnalysisResult

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "analyses"


def _ensure_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_analysis(result: AnalysisResult) -> Path:
    _ensure_dir()
    stock_dir = _DATA_DIR / result.stock_code
    stock_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{result.analysis_date}.json"
    filepath = stock_dir / filename
    tmp_path = stock_dir / f"{filename}.tmp"

    tmp_path.write_text(
        result.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8"
    )
    tmp_path.rename(filepath)
    logger.info(f"分析结果已保存: {filepath}")
    return filepath


def load_analysis(code: str, date: str) -> AnalysisResult | None:
    filepath = _DATA_DIR / code / f"{date}.json"
    if not filepath.exists():
        return None
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return AnalysisResult.model_validate(data)
    except Exception as e:
        logger.warning(f"加载分析结果失败: {filepath}, error={e}")
        return None


def list_analyses(code: str) -> list[dict]:
    stock_dir = _DATA_DIR / code
    if not stock_dir.exists():
        return []
    results = []
    for filepath in sorted(stock_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            results.append({
                "stock_code": data.get("stock_code", code),
                "stock_name": data.get("stock_name", ""),
                "analysis_date": data.get("analysis_date", filepath.stem),
                "current_price": data.get("current_price"),
                "overall_rating": data.get("overall_rating"),
                "signal": data.get("signal"),
                "confidence": data.get("confidence"),
            })
        except Exception:
            continue
    return results


def list_all_analyses() -> list[dict]:
    _ensure_dir()
    results = []
    for stock_dir in sorted(_DATA_DIR.iterdir()):
        if not stock_dir.is_dir():
            continue
        for filepath in sorted(stock_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(filepath.read_text(encoding="utf-8"))
                results.append({
                    "stock_code": data.get("stock_code", stock_dir.name),
                    "stock_name": data.get("stock_name", ""),
                    "analysis_date": data.get("analysis_date", filepath.stem),
                    "current_price": data.get("current_price"),
                    "overall_rating": data.get("overall_rating"),
                    "signal": data.get("signal"),
                    "confidence": data.get("confidence"),
                })
            except Exception:
                continue
    # Sort by date descending
    results.sort(key=lambda x: x.get("analysis_date", ""), reverse=True)
    return results
