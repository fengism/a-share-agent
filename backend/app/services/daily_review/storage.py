import json
from pathlib import Path

from app.models.daily_review import DailyReviewHistoryItem, DailyReviewResult
from app.services.daily_review.formatter import normalize_llm_review

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "daily_reviews"


def _review_path(date: str) -> Path:
    return _DATA_DIR / f"{date}.json"


def save_daily_review(review: DailyReviewResult) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _review_path(review.date)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")
    tmp_path.replace(path)


def load_daily_review(date: str) -> DailyReviewResult | None:
    path = _review_path(date)
    if not path.exists():
        return None
    review = DailyReviewResult.model_validate_json(path.read_text(encoding="utf-8"))
    review.llm_review = normalize_llm_review(review.llm_review)
    return review


def list_daily_reviews() -> list[DailyReviewHistoryItem]:
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
