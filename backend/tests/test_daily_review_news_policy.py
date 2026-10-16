"""每日复盘新闻窗口过滤与政策事件归类（timing 标记、去重、排序）。"""

from __future__ import annotations

from datetime import date

from app.domain.news import NewsSearchItem
from app.modules.daily_review import news_policy

_TARGET = date(2026, 10, 14)


def _news(
    title: str,
    *,
    publish_time: str = "2026-10-14T09:30:00+08:00",
    content: str = "",
    source: str = "财联社",
    url: str = "https://www.cls.cn/detail/1",
) -> NewsSearchItem:
    return NewsSearchItem(
        title=title,
        content=content,
        source=source,
        publish_time=publish_time,
        url=url,
        author="作者",
        read_count=0,
        comment_count=0,
    )


def test_filter_keeps_only_news_within_two_day_window() -> None:
    items = [
        _news("盘前", publish_time="2026-10-11T10:00:00+08:00"),
        _news("两日前", publish_time="2026-10-12T10:00:00+08:00"),
        _news("当日", publish_time="2026-10-14T10:00:00+08:00"),
        _news("两日后", publish_time="2026-10-16T10:00:00+08:00"),
        _news("过远", publish_time="2026-10-18T10:00:00+08:00"),
    ]

    selected = news_policy.filter_news_for_review(items, _TARGET, use_realtime=False)

    assert [item.title for item in selected] == ["两日前", "当日", "两日后"]


def test_filter_normalizes_partial_publish_time() -> None:
    items = [_news("缺年份", publish_time="09-30 14:20")]

    selected = news_policy.filter_news_for_review(items, date(2026, 9, 30), use_realtime=False)

    assert selected[0].publish_time == "2026-09-30T14:20:00"


def test_filter_rejects_relative_time_for_historical_review() -> None:
    items = [_news("刚刚发布", publish_time="刚刚")]

    assert news_policy.filter_news_for_review(items, _TARGET, use_realtime=False) == []


def test_filter_respects_limit() -> None:
    items = [
        _news(f"新闻{index}", publish_time=f"2026-10-14T{index:02d}:00:00+08:00")
        for index in range(10)
    ]

    selected = news_policy.filter_news_for_review(items, _TARGET, use_realtime=False, limit=3)

    assert len(selected) == 3


def test_classify_marks_timing_against_target_date() -> None:
    items = [
        _news("国务院发布支持房地产政策", publish_time="2026-10-13T09:00:00+08:00"),
        _news("央行宣布降准", publish_time="2026-10-14T09:00:00+08:00"),
        _news("证监会发布新规", publish_time="2026-10-15T09:00:00+08:00"),
    ]

    classified = news_policy.classify_policy_news(items, target_date=_TARGET)

    timings = {item.title: item.timing for item in classified}
    assert timings == {
        "国务院发布支持房地产政策": "before",
        "央行宣布降准": "on_date",
        "证监会发布新规": "after",
    }


def test_classify_skips_listing_pages() -> None:
    items = [_news("宏观"), _news("滚动新闻"), _news("央行宣布降准")]

    classified = news_policy.classify_policy_news(items, target_date=_TARGET)

    assert [item.title for item in classified] == ["央行宣布降准"]


def test_classify_drops_market_news_without_sector_links() -> None:
    items = [_news("公司举办年度发布会"), _news("机器人板块午后异动")]

    classified = news_policy.classify_policy_news(items, target_date=_TARGET)

    assert [item.title for item in classified] == ["机器人板块午后异动"]
    assert classified[0].event_type == "market"
    assert classified[0].related_sectors == ["机器人"]


def test_classify_ranks_central_policy_above_sector_chatter() -> None:
    items = [
        _news("机器人板块午后异动"),
        _news("国务院常务会议部署稳增长政策", url="https://www.gov.cn/zhengce/1"),
    ]

    classified = news_policy.classify_policy_news(items, target_date=_TARGET)

    assert classified[0].title == "国务院常务会议部署稳增长政策"
    assert classified[0].event_type == "policy"


def test_classify_merges_corroborating_sources() -> None:
    items = [
        _news("央行宣布降准05个百分点", source="财联社", url="https://www.cls.cn/detail/1"),
        _news("央行宣布降准05个百分点", source="新华社", url="https://www.xinhuanet.com/a"),
    ]

    classified = news_policy.classify_policy_news(items, target_date=_TARGET)

    assert len(classified) == 1
    # 权威媒体域名优先作为主来源，另一家降级为佐证来源
    assert classified[0].source == "新华社"
    assert classified[0].corroborating_sources == ["财联社"]


def test_classify_marks_direction_from_keywords() -> None:
    items = [
        _news("央行宣布降准支持实体经济发展"),
        _news("监管趋严 部分公司被处罚"),
    ]

    classified = {item.title: item.direction for item in news_policy.classify_policy_news(items, target_date=_TARGET)}

    assert classified["央行宣布降准支持实体经济发展"] == "positive"
    assert classified["监管趋严 部分公司被处罚"] == "negative"
