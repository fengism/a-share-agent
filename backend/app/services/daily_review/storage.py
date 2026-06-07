import json
from pathlib import Path

from app.models.daily_review import DailyReviewHistoryItem, DailyReviewResult
from app.services.daily_review.formatter import normalize_llm_review

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "daily_reviews"


def _review_path(date: str) -> Path:
    """根据日期生成复盘报告文件路径。

    Param:
        date: 复盘日期，格式 YYYY-MM-DD
    Return:
        复盘报告 JSON 文件路径
    """
    return _DATA_DIR / f"{date}.json"


def save_daily_review(review: DailyReviewResult) -> None:
    """将复盘结果以 JSON 格式原子写入本地文件。

    Param:
        review: 复盘结果对象
    Return:
        无
    """
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _review_path(review.date)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")
    tmp_path.replace(path)


def load_daily_review(date: str) -> DailyReviewResult | None:
    """从本地文件加载指定日期的复盘报告。

    Param:
        date: 复盘日期，格式 YYYY-MM-DD
    Return:
        复盘结果对象，文件不存在时返回 None
    """
    path = _review_path(date)
    if not path.exists():
        return None
    review = DailyReviewResult.model_validate_json(path.read_text(encoding="utf-8"))
    review.llm_review = normalize_llm_review(review.llm_review)
    return review


def list_daily_reviews() -> list[DailyReviewHistoryItem]:
    """列出所有已保存的复盘报告摘要，按日期倒序排列。

    Param:
        无
    Return:
        复盘历史摘要列表
    """
    if not _DATA_DIR.exists():
        return []

    items: list[DailyReviewHistoryItem] = []
    for path in sorted(_DATA_DIR.glob("*.json"), reverse=True):
        review = DailyReviewResult.model_validate_json(path.read_text(encoding="utf-8"))
        items.append(
            DailyReviewHistoryItem(
                date=review.date,
                title=review.title,
                generated_at=review.generated_at,
                market_summary=review.market_summary,
            )
        )
    return items
