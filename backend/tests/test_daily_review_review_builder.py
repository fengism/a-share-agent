"""每日复盘快照构建与 Prompt 渲染：缺数据兜底、占位符全覆盖、事件时点标记。"""

from __future__ import annotations

import re

from app.domain.news import NewsSearchItem
from app.financial_data.market.quotes.schemas import MarketStatistics
from app.modules.daily_review import review_builder
from app.modules.daily_review.models import DailyReviewSourceStatus, PolicyNewsSnapshotItem
from app.modules.daily_review.prompts import MARKET_USER_PROMPT


def _news_item(
    title: str,
    *,
    content: str = "",
    source: str = "财联社",
    publish_time: str = "2026-10-15T09:30:00+08:00",
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


def _empty_snapshot(**kwargs: object):
    return review_builder.build_snapshot(
        None, None, None, None, None, None, None, None, None, **kwargs  # type: ignore[arg-type]
    )


def test_build_snapshot_tolerates_missing_sources() -> None:
    snapshot = _empty_snapshot()

    assert snapshot.indices == []
    assert snapshot.market_news == []
    assert snapshot.market_statistics == {}
    assert snapshot.macro_data == {}


def test_build_snapshot_tolerates_exception_values() -> None:
    snapshot = review_builder.build_snapshot(
        RuntimeError("indices 不可用"),
        TimeoutError("热股超时"),
        None,
        None,
        None,
        RuntimeError("统计失败"),
        RuntimeError("新闻失败"),
        None,
        None,
    )

    assert snapshot.indices == []
    assert snapshot.hot_stocks == []
    assert snapshot.market_statistics == {}
    assert snapshot.market_news == []


def test_build_snapshot_splits_sector_rankings_without_mutating_source() -> None:
    statistics = MarketStatistics(
        date="2026-10-14",
        top_sectors=[{"name": "机器人", "change_pct": 4.2}],
        bottom_sectors=[{"name": "煤炭", "change_pct": -2.1}],
        up_count=3200,
    )

    snapshot = review_builder.build_snapshot(
        None, None, None, None, None, statistics, None, None, None  # type: ignore[arg-type]
    )

    assert snapshot.top_sectors == [{"name": "机器人", "change_pct": 4.2}]
    assert snapshot.bottom_sectors == [{"name": "煤炭", "change_pct": -2.1}]
    assert "top_sectors" not in snapshot.market_statistics
    assert snapshot.market_statistics["up_count"] == 3200
    # 原始对象不被就地修改
    assert statistics.top_sectors == [{"name": "机器人", "change_pct": 4.2}]


def test_build_prompt_fills_every_placeholder_on_empty_snapshot() -> None:
    prompt = review_builder.build_prompt("2026-10-14", _empty_snapshot(), MARKET_USER_PROMPT)

    assert re.search(r"\{[a-z_]+\}", prompt) is None
    assert "2026-10-14" in prompt


def test_build_prompt_renders_source_status_dates_and_dates_aliases() -> None:
    snapshot = _empty_snapshot(
        requested_date="2026-10-14",
        effective_date="2026-10-13",
        source_status={
            "market_news": DailyReviewSourceStatus(status="partial", data_date="2026-10-13"),
            "macro_data": DailyReviewSourceStatus(status="unavailable", error="上游不可用"),
        },
    )

    prompt = review_builder.build_prompt("2026-10-14", snapshot, MARKET_USER_PROMPT)

    assert "2026-10-13" in prompt
    assert "上游不可用" in prompt


def test_build_prompt_marks_macro_pending_and_after_timing_events() -> None:
    snapshot = _empty_snapshot(
        macro_analysis={
            "summary": "综述",
            "sentiment": "中性",
            "pending_count": 1,
            "degraded": False,
            "events": [
                {"date": "2026-10-15", "category": "其他", "title": "未来事件", "pending": True},
            ],
        },
        policy_news=[
            PolicyNewsSnapshotItem(
                title="次日政策细则落地",
                event_type="policy",
                direction="mixed",
                timing="after",
                related_sectors=["新能源车"],
                source="财联社",
                publish_time="2026-10-15T09:00:00+08:00",
            ),
        ],
    )

    prompt = review_builder.build_prompt("2026-10-14", snapshot, MARKET_USER_PROMPT)

    assert "未来事件（待解读）" in prompt
    assert "事后验证" in prompt
    assert "次日政策细则落地" in prompt


def test_build_prompt_lists_policy_news_once() -> None:
    policy = PolicyNewsSnapshotItem(
        title="央行降准释放流动性",
        content="央行决定下调存款准备金率 0.5 个百分点，释放长期资金约 1 万亿元。",
        source="新华社",
        publish_time="2026-10-15T09:00:00+08:00",
        url="https://example.com/policy-1",
        event_type="policy",
        direction="positive",
    )
    snapshot = review_builder.build_snapshot(
        None,
        None,
        None,
        None,
        None,
        None,
        [
            _news_item(
                title=policy.title,
                content="冗" * 400,
                source=policy.source,
                publish_time=policy.publish_time or "",
                url=policy.url,
            ),
            _news_item(
                title="某公司发布三季报",
                content="净利润同比增长 30%",
                publish_time="2026-10-15T10:00:00+08:00",
                url="https://example.com/news-2",
            ),
        ],
        None,
        None,
        policy_news=[policy],
    )

    prompt = review_builder.build_prompt("2026-10-15", snapshot, MARKET_USER_PROMPT)

    # 同一篇既在政策事件里又出现在市场新闻里会重复占用 token 并诱发重复计入。
    assert prompt.count(policy.title) == 1
    assert prompt.count("某公司发布三季报") == 1
    assert "内容:央行决定下调存款准备金率" in prompt
    assert "冗" * 400 not in prompt


def test_build_prompt_notes_when_all_news_are_policy_events() -> None:
    policy = PolicyNewsSnapshotItem(
        title="国常会部署扩大内需",
        content="会议部署扩大内需若干措施。",
        source="新华社",
        url="https://example.com/policy-2",
    )
    snapshot = review_builder.build_snapshot(
        None,
        None,
        None,
        None,
        None,
        None,
        [_news_item(title=policy.title, content="会议部署了若干措施。", source=policy.source, url=policy.url)],
        None,
        None,
        policy_news=[policy],
    )

    prompt = review_builder.build_prompt("2026-10-15", snapshot, MARKET_USER_PROMPT)

    assert prompt.count(policy.title) == 1
    assert "暂无其他市场新闻" in prompt


# --------------------------------------------------------------------------- #
# 量化锚点：数字全部由 Python 预计算，模型只做解读。
# --------------------------------------------------------------------------- #


def _anchor_snapshot(**kwargs: object):
    from app.modules.daily_review.models import DailyReviewDataSnapshot

    return DailyReviewDataSnapshot(**kwargs)  # type: ignore[arg-type]


def _ladder(stocks: list[dict], sectors: list[dict] | None = None) -> dict:
    return {"stocks": stocks, "sectors": sectors or []}


def test_quant_anchors_compute_break_rate_and_ladder_structure() -> None:
    snapshot = _anchor_snapshot(
        limit_up_ladder=_ladder(
            [
                {"name": "甲", "board_count": 6, "sector_name": "机器人", "one_word": True},
                {"name": "乙", "board_count": 2, "sector_name": "机器人"},
                {"name": "丙", "board_count": 2, "sector_name": "算力"},
                *[{"name": f"首板{i}", "board_count": 1, "sector_name": "机器人"} for i in range(7)],
            ],
            [{"sector_name": "机器人", "stock_count": 8}, {"sector_name": "算力", "stock_count": 2}],
        ),
        limit_break_pool={"items": [{"code": "000001", "open_times": 2}, {"code": "000002", "open_times": 1}]},
    )

    anchors = review_builder._quant_anchors(snapshot)

    assert "涨停 10 家（首板 7 家、二板及以上 3 家）" in anchors
    assert "空间板 6 板（甲）" in anchors
    assert "一字板 1 家" in anchors
    assert "梯队断层：3板、4板、5板 无个股" in anchors
    assert "炸板 2 家，炸板率 16.7%（炸板 2 / 触及涨停 12）" in anchors
    assert "Top3 板块 10 家，占全市场涨停 100%" in anchors


def test_quant_anchors_declare_break_rate_unavailable() -> None:
    snapshot = _anchor_snapshot(
        limit_up_ladder=_ladder([{"name": "甲", "board_count": 2}]),
    )

    anchors = review_builder._quant_anchors(snapshot)

    assert "炸板率不可得" in anchors
    assert "严禁估算" in anchors


def test_quant_anchors_report_volume_multiples() -> None:
    snapshot = _anchor_snapshot(
        market_volume={
            "amount": 1_0000_0000_0000.0,
            "amount_before_one_day": 8000_0000_0000.0,
            "amount_average_20_day": 5000_0000_0000.0,
            "amount_average_60_day": 4000_0000_0000.0,
        }
    )

    anchors = review_builder._quant_anchors(snapshot)

    assert "成交额 10000 亿" in anchors
    assert "较前一交易日 +25.0%" in anchors
    assert "为 20 日均值 2.00 倍" in anchors
    assert "为 60 日均值 2.50 倍" in anchors


def test_quant_anchors_flag_northbound_and_breadth_divergence() -> None:
    snapshot = _anchor_snapshot(
        indices=[{"name": "上证指数", "change_pct": 1.0, "price": 3300.0, "high": 3320.0, "low": 3280.0, "amplitude": 1.2}],
        northbound_funds={"north_money": -50.0},
        market_statistics={"up_count": 1000, "down_count": 3000, "limit_up_count": 20, "limit_down_count": 8},
    )

    anchors = review_builder._quant_anchors(snapshot)

    assert "北向 -50.00 亿（净卖出）vs 指数 上涨（均值 +1.00%），方向背离" in anchors
    assert "指数上涨但下跌家数（3000）多于上涨家数（1000），存在宽度背离" in anchors
    assert "收盘位于当日振幅 50%" in anchors


def test_build_prompt_includes_quant_anchors_block() -> None:
    snapshot = _anchor_snapshot(
        limit_up_ladder=_ladder([{"name": "甲", "board_count": 3}]),
        limit_break_pool={"items": []},
        effective_date="2026-10-15",
    )

    prompt = review_builder.build_prompt("2026-10-15", snapshot, MARKET_USER_PROMPT)

    assert "# 量化锚点" in prompt
    assert "空间板 3 板" in prompt
    assert "炸板 0 家，炸板率 0.0%" in prompt
    assert re.search(r"\{[a-z_]+\}", prompt) is None


# --------------------------------------------------------------------------- #
# 深度输出：情绪周期 / 三情景预案 / 次日观察锚点 / 关键点位
# --------------------------------------------------------------------------- #


def _section():
    from app.modules.daily_review.models import DailyReviewSection

    return DailyReviewSection(title="小节", summary="摘要")


def _prompt_output(**kwargs: object):
    from app.modules.daily_review.prompts import DailyReviewPromptOutput

    return DailyReviewPromptOutput(
        market_summary="摘要",
        sentiment_cycle={"stage": "冰点"},
        index_review=_section(),
        hotspot_review=_section(),
        dragon_tiger_review=_section(),
        news_policy_review=_section(),
        **kwargs,  # type: ignore[arg-type]
    )


def test_prompt_output_requires_sentiment_cycle() -> None:
    import pytest
    from pydantic import ValidationError

    from app.modules.daily_review.prompts import DailyReviewPromptOutput

    with pytest.raises(ValidationError, match="sentiment_cycle"):
        DailyReviewPromptOutput(
            market_summary="摘要",
            index_review=_section(),
            hotspot_review=_section(),
            dragon_tiger_review=_section(),
            news_policy_review=_section(),
        )


def test_prompt_output_truncates_and_dedupes_deep_fields() -> None:
    output = _prompt_output(
        scenario_plans=[
            {"name": "超预期"},
            {"name": "超预期"},
            {"name": "符合预期"},
            {"name": "低于预期"},
            {"name": "低于预期"},
        ],
        next_day_watchlist=[
            {"name": "甲"},
            {"name": "   "},
            {"name": "乙"},
            {"name": "丙"},
            {"name": "丁"},
        ],
        key_levels=["上证 3250 支撑", " ", "成交额重回 1.5 万亿"],
        risk_alerts=[f"风险{i}" for i in range(12)],
        event_impacts=[],
    )

    assert [item.name for item in output.scenario_plans] == ["超预期", "符合预期", "低于预期"]
    assert [item.name for item in output.next_day_watchlist] == ["甲", "乙", "丙"]
    assert output.key_levels == ["上证 3250 支撑", "成交额重回 1.5 万亿"]
    assert len(output.risk_alerts) == 8


def test_ground_watchlist_drops_unknown_names() -> None:
    from app.modules.daily_review.models import DailyReviewWatchItem

    snapshot = _anchor_snapshot(
        limit_up_ladder=_ladder([{"name": "甲", "board_count": 3}, {"name": "乙", "board_count": 1}])
    )

    kept = review_builder.ground_watchlist(
        snapshot,
        [DailyReviewWatchItem(name="虚构股"), DailyReviewWatchItem(name="甲")],
    )

    assert [item.name for item in kept] == ["甲"]


def test_ground_watchlist_falls_back_to_real_space_board() -> None:
    from app.modules.daily_review.models import DailyReviewWatchItem

    snapshot = _anchor_snapshot(
        limit_up_ladder=_ladder([{"name": "甲", "board_count": 5}, {"name": "乙", "board_count": 2}])
    )

    kept = review_builder.ground_watchlist(snapshot, [DailyReviewWatchItem(name="虚构股")])

    assert [item.name for item in kept] == ["甲"]
    assert kept[0].role == "连板最高板"


def test_ground_watchlist_returns_empty_without_ladder() -> None:
    assert review_builder.ground_watchlist(_anchor_snapshot(), []) == []


def test_markdown_renders_deep_sections() -> None:
    from app.modules.daily_review import report_renderer
    from app.modules.daily_review.models import (
        DailyReviewScenario,
        DailyReviewSentimentCycle,
        DailyReviewWatchItem,
    )

    review = review_builder.build_fallback_review(
        "2026-10-15", _anchor_snapshot(), "2026-10-15T16:00:00+08:00"
    )
    review.sentiment_cycle = DailyReviewSentimentCycle(
        stage="修复回暖", ladder_health="梯队健康晋级", evidence=["空间板 4 板", "炸板率 8.0%"]
    )
    review.scenario_plans = [
        DailyReviewScenario(name="超预期", trigger="放量高开", playbook="加仓主线", watch_levels=["成交额 1.5 万亿"])
    ]
    review.next_day_watchlist = [
        DailyReviewWatchItem(name="甲", role="总龙头", reason="主线龙头", trigger="竞价高开")
    ]
    review.key_levels = ["上证 3250 支撑"]

    markdown = report_renderer.render_daily_review_markdown(review)

    assert "#### 情绪周期定位：修复回暖" in markdown
    assert "- 依据：空间板 4 板" in markdown
    assert "#### 明日三情景预案" in markdown
    assert "**超预期**：触发 放量高开；应对 加仓主线" in markdown
    assert "观察信号：成交额 1.5 万亿" in markdown
    assert "#### 次日观察锚点" in markdown
    assert "**甲**（总龙头）" in markdown
    assert "#### 关键点位与量能阈值" in markdown
    assert "上证 3250 支撑" in markdown


def test_markdown_renders_self_check_and_cycle_trend() -> None:
    from app.modules.daily_review import cycle_trend, report_renderer
    from app.modules.daily_review.models import (
        DailyReviewCycleRecord,
        DailyReviewIndexCheck,
        DailyReviewIndexMove,
        DailyReviewPreviousCheck,
        DailyReviewWatchCheck,
    )

    review = review_builder.build_fallback_review(
        "2026-10-15", _anchor_snapshot(), "2026-10-15T16:00:00+08:00"
    )
    review.previous_review_check = DailyReviewPreviousCheck(
        review_date="2026-10-14",
        verified_date="2026-10-15",
        indices=[
            DailyReviewIndexCheck(
                code="000001", name="上证指数", previous_change_pct=1.0, change_pct=-0.5
            )
        ],
        watchlist=[
            DailyReviewWatchCheck(name="甲", code="000001", role="总龙头", change_pct=3.2, hit=True),
            DailyReviewWatchCheck(name="乙", code="600000", role="中军容量票", missing=True),
        ],
        hit_count=1,
        checked_count=1,
        hit_rate=1.0,
        previous_stage="修复回暖",
        limit_up_count=48,
        previous_limit_up_count=60,
        limit_up_delta=-12,
        note="部分观察标的次日无行情（停牌或未入库）",
    )
    review.cycle_trend = cycle_trend.build_cycle_trend(
        [
            DailyReviewCycleRecord(
                date="2026-10-13",
                stage="冰点",
                indices=[DailyReviewIndexMove(code="000001", name="上证指数", change_pct=-1.2)],
                limit_up_count=31,
                break_rate=0.25,
            ),
            DailyReviewCycleRecord(
                date="2026-10-14",
                stage="修复回暖",
                indices=[DailyReviewIndexMove(code="000001", name="上证指数", change_pct=1.0)],
                limit_up_count=60,
                break_rate=0.12,
            ),
        ]
    )

    markdown = report_renderer.render_daily_review_markdown(review)

    assert "## 上一交易日复盘自检（2026-10-14 → 2026-10-15）" in markdown
    assert "- 上一交易日周期定位：修复回暖" in markdown
    assert "- 涨停家数：60 → 48" in markdown
    assert "- 上证指数：+1.00% → -0.50%" in markdown
    assert "- 甲：次日 +3.20%（命中）" in markdown
    assert "- 乙：次日行情缺失" in markdown
    assert "- 观察标的命中率：1/1（1.00%）" in markdown
    assert "## 情绪周期历史趋势" in markdown
    assert "2026-10-13；冰点；涨停 31 家；炸板率 25.0%；指数 -1.20%；次日指数 +1.00%" in markdown
    assert "2026-10-14；修复回暖；涨停 60 家" in markdown
    assert "- 阶段统计：冰点 出现 1 次" in markdown


def test_markdown_omits_history_sections_without_data() -> None:
    from app.modules.daily_review import report_renderer

    review = review_builder.build_fallback_review(
        "2026-10-15", _anchor_snapshot(), "2026-10-15T16:00:00+08:00"
    )

    markdown = report_renderer.render_daily_review_markdown(review)

    assert "## 上一交易日复盘自检" not in markdown
    assert "## 情绪周期历史趋势" not in markdown
