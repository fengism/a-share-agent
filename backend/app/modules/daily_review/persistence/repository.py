from pathlib import Path

from app.configuration.paths import DATA_DIR
from app.infrastructure.persistence.json_storage import atomic_write_text
from app.modules.daily_review.formatter import normalize_llm_review
from app.modules.daily_review.models import DailyReviewResult
from app.modules.daily_review.schemas import DailyReviewHistoryItem

_DATA_DIR = DATA_DIR / "daily_reviews"


def _legacy_review_path(date: str) -> Path:
    """根据日期生成旧版全局复盘报告文件路径。

    Param:
        date: 复盘日期，格式 YYYY-MM-DD
    Return:
        复盘报告 JSON 文件路径
    """
    return _DATA_DIR / f"{date}.json"


def _user_review_path(date: str, user_id: int) -> Path:
    """根据用户和日期生成复盘报告文件路径。"""
    return _DATA_DIR / "users" / str(user_id) / f"{date}.json"


def _load_review(path: Path) -> DailyReviewResult:
    review = DailyReviewResult.model_validate_json(path.read_text(encoding="utf-8"))
    review.llm_review = normalize_llm_review(review.llm_review)
    return review


def save_daily_review(review: DailyReviewResult, user_id: int) -> None:
    """将复盘结果以 JSON 格式原子写入本地文件。

    Param:
        review: 复盘结果对象
        user_id: 当前用户 ID
    Return:
        无
    """
    path = _user_review_path(review.date, user_id)
    atomic_write_text(path, review.model_dump_json(indent=2))


def load_daily_review(date: str, user_id: int) -> DailyReviewResult | None:
    """从本地文件加载指定日期的复盘报告。

    Param:
        date: 复盘日期，格式 YYYY-MM-DD
        user_id: 当前用户 ID
    Return:
        复盘结果对象，文件不存在时返回 None
    """
    user_path = _user_review_path(date, user_id)
    if user_path.exists():
        return _load_review(user_path)
    legacy_path = _legacy_review_path(date)
    if legacy_path.exists():
        return _load_review(legacy_path)
    return None


def delete_daily_review(
    date: str,
    user_id: int,
    can_delete_legacy: bool = False,
) -> bool:
    """删除当前用户复盘；管理员可在用户复盘不存在时删除旧版全局复盘。"""
    if len(date) != 10 or date[4] != "-" or date[7] != "-" or not date.replace("-", "").isdigit():
        return False

    path = _user_review_path(date, user_id)
    if not path.is_file():
        if not can_delete_legacy:
            return False
        path = _legacy_review_path(date)
        if not path.is_file():
            return False

    path.unlink()
    return True


def list_daily_reviews(
    user_id: int,
    limit: int = 100,
    offset: int = 0,
    can_delete_legacy: bool = False,
) -> list[DailyReviewHistoryItem]:
    """列出所有已保存的复盘报告摘要，按日期倒序排列。

    Param:
        user_id: 当前用户 ID
    Return:
        复盘历史摘要列表
    """
    if not _DATA_DIR.exists():
        return []

    paths_by_date: dict[str, Path] = {}
    for path in _DATA_DIR.glob("*.json"):
        paths_by_date[path.stem] = path
    user_dir = _DATA_DIR / "users" / str(user_id)
    if user_dir.exists():
        for path in user_dir.glob("*.json"):
            paths_by_date[path.stem] = path

    dates = sorted(paths_by_date, reverse=True)[offset:offset + limit]
    reviews = [_load_review(paths_by_date[date]) for date in dates]

    return [
        DailyReviewHistoryItem(
            date=review.date,
            title=review.title,
            generated_at=review.generated_at,
            market_summary=review.market_summary,
            can_delete=paths_by_date[date].parent == user_dir or can_delete_legacy,
        )
        for date, review in zip(dates, reviews, strict=True)
    ]
