"""每日复盘管线：缓存失效策略、质量分级、共享缓存/串行与政策新闻复用。"""

from __future__ import annotations

import asyncio
import inspect
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.configuration.schema import Settings
from app.core.cache import analysis_cache
from app.domain.news import NewsSearchItem
from app.domain.prompting import PromptTrace
from app.financial_data.market.macro.schemas import MacroAnalysisResponse
from app.infrastructure.llm.prompting import PromptRun
from app.modules.daily_review import collector, news_policy, pipeline, report_renderer, review_builder, web_policy_news
from app.modules.daily_review.collector import DailyReviewCollection
from app.modules.daily_review.models import (
    DAILY_REVIEW_SCHEMA_VERSION,
    DailyReviewCycleRecord,
    DailyReviewDataSnapshot,
    DailyReviewResult,
    DailyReviewScenario,
    DailyReviewSection,
    DailyReviewSentimentCycle,
    DailyReviewSourceStatus,
    DailyReviewWatchItem,
    PolicyNewsSnapshotItem,
)
from app.modules.daily_review.prompts import DailyReviewPromptOutput
from app.modules.daily_review.schemas import DailyReviewRequest
from app.runtime import workflow_worker

_TZ = ZoneInfo("Asia/Shanghai")


def _section() -> DailyReviewSection:
    return DailyReviewSection(title="章节", summary="摘要")


def _result(
    *,
    snapshot: DailyReviewDataSnapshot | None = None,
    schema_version: int = DAILY_REVIEW_SCHEMA_VERSION,
    generation_status: str = "llm",
    llm_error: str = "",
    minutes_ago: float = 0.0,
) -> DailyReviewResult:
    generated_at = datetime.now(_TZ) - timedelta(minutes=minutes_ago)
    return DailyReviewResult(
        schema_version=schema_version,
        date="2026-10-14",
        effective_date="2026-10-14",
        quality_status="complete",
        generation_status=generation_status,  # type: ignore[arg-type]
        llm_error=llm_error,
        title="每日复盘",
        generated_at=generated_at.isoformat(timespec="seconds"),
        market_summary="摘要",
        index_review=_section(),
        hotspot_review=_section(),
        dragon_tiger_review=_section(),
        data_snapshot=snapshot or DailyReviewDataSnapshot(),
    )


def _source(status: str, error: str = "") -> DailyReviewSourceStatus:
    return DailyReviewSourceStatus(status=status, error=error)  # type: ignore[arg-type]


def _macro_analysis(pending_count: int = 0, degraded: bool = False) -> dict:
    return {"summary": "综述", "sentiment": "中性", "pending_count": pending_count, "degraded": degraded, "events": []}


async def test_staleness_flags_legacy_schema() -> None:
    review = _result(schema_version=DAILY_REVIEW_SCHEMA_VERSION - 1)

    assert await pipeline._cached_review_staleness(review) == "schema_outdated"


async def test_staleness_accepts_complete_review() -> None:
    snapshot = DailyReviewDataSnapshot(
        source_status={"market_news": _source("complete")},
        macro_analysis=_macro_analysis(),
    )

    assert await pipeline._cached_review_staleness(_result(snapshot=snapshot)) is None


async def test_staleness_retries_llm_fallback_after_cooldown() -> None:
    snapshot = DailyReviewDataSnapshot(
        source_status={"market_news": _source("complete")},
        macro_analysis=_macro_analysis(),
    )
    fresh = _result(snapshot=snapshot, generation_status="fallback", minutes_ago=1)
    stale = _result(snapshot=snapshot, generation_status="fallback", minutes_ago=30)

    assert await pipeline._cached_review_staleness(fresh) is None
    assert await pipeline._cached_review_staleness(stale) == "llm_fallback"


async def test_staleness_never_retries_missing_api_key() -> None:
    snapshot = DailyReviewDataSnapshot(
        source_status={"market_news": _source("complete")},
        macro_analysis=_macro_analysis(),
    )
    review = _result(
        snapshot=snapshot,
        generation_status="fallback",
        llm_error="深度分析 缺少 API Key，请在设置页填写个人 API Key。",
        minutes_ago=600,
    )

    assert await pipeline._cached_review_staleness(review) is None


@pytest.mark.parametrize(
    ("cached_macro", "current", "expected"),
    [
        ({"pending_count": 2, "degraded": False}, {"pending_count": 0, "degraded": False}, "macro_analysis_ready"),
        ({"pending_count": 2, "degraded": False}, {"pending_count": 1, "degraded": False}, None),
        ({"pending_count": 0, "degraded": True}, {"pending_count": 0, "degraded": True}, None),
        ({"pending_count": 0, "degraded": False}, {"pending_count": 0, "degraded": False}, None),
    ],
)
async def test_staleness_refreshes_only_when_macro_ready(
    monkeypatch: pytest.MonkeyPatch,
    cached_macro: dict,
    current: dict,
    expected: str | None,
) -> None:
    async def _fake_macro(days: int = 31) -> MacroAnalysisResponse:
        return MacroAnalysisResponse(
            period="2026-09-14 ~ 2026-10-15",
            summary="综述",
            sentiment="中性",
            events=[{"date": "2026-10-14", "category": "物价", "title": "CPI", "interpretation": "解读", "impact": "偏多"}],
            pending_count=current["pending_count"],
            degraded=current["degraded"],
        )

    monkeypatch.setattr(pipeline, "get_macro_analysis", _fake_macro)
    snapshot = DailyReviewDataSnapshot(
        source_status={"market_news": _source("complete")},
        macro_analysis={"summary": "综述", "events": [], **cached_macro},
    )
    review = _result(snapshot=snapshot, minutes_ago=30)

    assert await pipeline._cached_review_staleness(review) == expected


async def test_staleness_flags_unavailable_news() -> None:
    snapshot = DailyReviewDataSnapshot(
        source_status={
            "market_news": _source("unavailable", "复盘日前后 2 天没有可核验发布时间的本地或 Web Search 财经政策新闻")
        },
        macro_analysis=_macro_analysis(),
    )

    assert await pipeline._cached_review_staleness(_result(snapshot=snapshot)) == "market_news_unavailable"


async def test_staleness_retries_thin_partial_news_after_long_cooldown() -> None:
    snapshot = DailyReviewDataSnapshot(
        source_status={"market_news": _source("partial", "内置新闻数量不足")},
        macro_analysis=_macro_analysis(),
        policy_news=[],
    )

    recent = _result(snapshot=snapshot, minutes_ago=60)
    old = _result(snapshot=snapshot, minutes_ago=60 * 12)

    assert await pipeline._cached_review_staleness(recent) is None
    assert await pipeline._cached_review_staleness(old) == "news_policy_empty"


def test_quality_marks_auxiliary_gaps_as_notes() -> None:
    snapshot = DailyReviewDataSnapshot(
        source_status={
            "indices": _source("complete"),
            "market_statistics": _source("complete"),
            "market_volume": _source("complete"),
            "market_news": _source("complete"),
            "macro_analysis": _source("partial", "2 条宏观事件待后台解读，暂展示原文"),
            "hot_stocks": _source("unavailable", "热门股票榜不可用"),
        }
    )

    quality, warnings, notes, errors = pipeline._quality(snapshot)

    assert quality == "complete"
    assert warnings == []
    assert "macro_analysis：数据部分可用" in notes
    assert "hot_stocks：热门股票榜不可用" in notes
    assert set(errors) == {"hot_stocks"}


def test_quality_degrades_on_core_source_gap() -> None:
    snapshot = DailyReviewDataSnapshot(
        source_status={
            "indices": _source("unavailable", "指数数据缺失"),
            "market_statistics": _source("complete"),
            "market_volume": _source("complete"),
            "market_news": _source("complete"),
            "macro_analysis": _source("partial", "待解读"),
        }
    )

    quality, warnings, notes, errors = pipeline._quality(snapshot)

    assert quality == "degraded"
    assert warnings[0] == "核心复盘数据缺失：indices"
    assert "indices：指数数据缺失" in warnings
    assert all("macro_analysis" not in item for item in warnings)
    assert "macro_analysis：数据部分可用" in notes
    assert errors == {"indices": "指数数据缺失"}


def test_markdown_renders_warnings_and_notes() -> None:
    review = _result()
    review.warnings = ["核心复盘数据缺失：indices"]
    review.notes = ["macro_analysis：数据部分可用"]

    text = report_renderer.render_daily_review_markdown(review)

    assert "## 数据覆盖与核验状态" in text
    assert "- ⚠️ 核心复盘数据缺失：indices" in text
    assert "- 说明：macro_analysis：数据部分可用" in text


def test_markdown_keeps_clean_fallback_without_gaps() -> None:
    text = report_renderer.render_daily_review_markdown(_result())

    assert "- 核心数据维度未发现明确缺口。" in text
    assert "⚠️" not in text


def _collection(*, statuses: dict[str, DailyReviewSourceStatus] | None = None) -> DailyReviewCollection:
    default_statuses = {
        "indices": _source("complete"),
        "market_statistics": _source("complete"),
        "market_volume": _source("complete"),
        "market_news": _source("complete"),
    }
    return DailyReviewCollection(values={}, source_status=statuses or default_statuses)


def _prompt_run(summary: str = "AI 摘要") -> PromptRun[DailyReviewPromptOutput]:
    return PromptRun(
        value=DailyReviewPromptOutput(
            market_summary=summary,
            sentiment_cycle=DailyReviewSentimentCycle(stage="主升共振", evidence=["空间板 6 板"]),
            scenario_plans=[
                DailyReviewScenario(name="超预期", trigger="放量高开", playbook="加仓主线"),
                DailyReviewScenario(name="符合预期", trigger="平开震荡", playbook="持股待涨"),
                DailyReviewScenario(name="低于预期", trigger="低开走弱", playbook="降仓防守"),
            ],
            index_review=_section(),
            hotspot_review=_section(),
            dragon_tiger_review=_section(),
            news_policy_review=_section(),
        ),
        trace=PromptTrace(
            prompt_id="daily_review_analysis",
            prompt_version="1.6.0",
            input_digest="digest",
            generated_at="2026-10-14T15:00:00+08:00",
        ),
    )


def _historical_resolution() -> pipeline.DailyReviewDateResolution:
    return pipeline.DailyReviewDateResolution(
        requested_date=date(2026, 10, 14),
        effective_date=date(2026, 10, 14),
        session_status="completed",
        use_realtime=False,
    )


async def test_generation_lock_is_shared_per_date_and_user() -> None:
    pipeline._generation_locks.clear()

    first = await pipeline._generation_lock(("2026-10-14", 7))

    assert await pipeline._generation_lock(("2026-10-14", 7)) is first
    assert await pipeline._generation_lock(("2026-10-14", 8)) is not first
    assert await pipeline._generation_lock(("2026-10-13", 7)) is not first


async def test_collection_snapshot_is_shared_for_both_session_kinds(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis_cache.clear()
    calls: list[str] = []

    async def _fake_collect(target_date: date, *, use_realtime: bool) -> DailyReviewCollection:
        calls.append(f"{target_date.isoformat()}:{use_realtime}")
        return _collection()

    monkeypatch.setattr(pipeline, "collect_daily_review_data", _fake_collect)
    realtime_resolution = pipeline.DailyReviewDateResolution(
        requested_date=date(2026, 10, 15),
        effective_date=date(2026, 10, 15),
        session_status="completed",
        use_realtime=True,
    )

    await pipeline._collect_shared(_historical_resolution())
    await pipeline._collect_shared(_historical_resolution())
    assert calls == ["2026-10-14:False"]

    # 收盘后的当日口径（use_realtime=True）同样跨用户共享，避免晚间重复采集。
    await pipeline._collect_shared(realtime_resolution)
    await pipeline._collect_shared(realtime_resolution)
    assert calls == ["2026-10-14:False", "2026-10-15:True"]


async def test_review_prompt_cache_reuses_identical_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis_cache.clear()
    prompts: list[str] = []

    async def _fake_run(spec: object, context: dict, **kwargs: object) -> PromptRun[DailyReviewPromptOutput]:
        prompts.append(str(context["prompt"]))
        return _prompt_run(f"摘要{len(prompts)}")

    monkeypatch.setattr(pipeline, "run_structured_prompt", _fake_run)
    settings = Settings()

    first = await pipeline._run_review_prompt("PROMPT", settings, allow_cache=True)
    second = await pipeline._run_review_prompt("PROMPT", settings, allow_cache=True)

    assert len(prompts) == 1
    assert second.value.market_summary == "摘要1" == first.value.market_summary

    forced = await pipeline._run_review_prompt("PROMPT", settings, allow_cache=False)

    assert len(prompts) == 2
    assert forced.value.market_summary == "摘要2"


def test_review_llm_cache_key_separates_models() -> None:
    assert pipeline._review_llm_cache_key("PROMPT", Settings()) == pipeline._review_llm_cache_key("PROMPT", Settings())
    assert pipeline._review_llm_cache_key("PROMPT", Settings()) != pipeline._review_llm_cache_key(
        "PROMPT", Settings(llm_model="other-model")
    )
    assert pipeline._review_llm_cache_key("PROMPT", Settings()) != pipeline._review_llm_cache_key("其他 PROMPT", Settings())


async def test_generate_daily_review_serializes_duplicate_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis_cache.clear()
    pipeline._generation_locks.clear()
    pipeline._prompt_locks.clear()
    store: dict[tuple[str, int], DailyReviewResult] = {}
    prompts: list[str] = []

    async def _direct(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.pop("semaphore", None)
        return fn(*args, **kwargs)

    async def _fake_collect(target_date: date, *, use_realtime: bool) -> DailyReviewCollection:
        return _collection()

    async def _fake_run(spec: object, context: dict, **kwargs: object) -> PromptRun[DailyReviewPromptOutput]:
        prompts.append(str(context["prompt"]))
        # 让出事件循环：模拟真实 LLM 调用的耗时，使并发重复调用真正交错，
        # 否则 gather 的两个任务会串行跑完，测试会假通过。
        await asyncio.sleep(0)
        return _prompt_run()

    async def _fake_resolve(requested_date: date | None, *, now: object = None) -> pipeline.DailyReviewDateResolution:
        return _historical_resolution()

    monkeypatch.setattr(pipeline, "call_blocking", _direct)
    monkeypatch.setattr(pipeline, "collect_daily_review_data", _fake_collect)
    monkeypatch.setattr(pipeline, "run_structured_prompt", _fake_run)
    monkeypatch.setattr(pipeline, "resolve_daily_review_date", _fake_resolve)
    monkeypatch.setattr(pipeline, "load_daily_review", lambda date_text, user_id: store.get((date_text, user_id)))
    monkeypatch.setattr(
        pipeline,
        "save_daily_review",
        lambda review, user_id: store.__setitem__((review.effective_date, user_id), review),
    )

    results = await asyncio.gather(
        pipeline.generate_daily_review(DailyReviewRequest(date=date(2026, 10, 14)), 7),
        pipeline.generate_daily_review(DailyReviewRequest(date=date(2026, 10, 14)), 7),
    )

    assert len(prompts) == 1
    assert list(store) == [("2026-10-14", 7)]
    assert {result.market_summary for result in results} == {"AI 摘要"}


async def test_concurrent_users_share_one_llm_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """同一日同一模型下，不同用户同时首次生成也只真实调用一次 LLM。"""
    analysis_cache.clear()
    pipeline._generation_locks.clear()
    pipeline._prompt_locks.clear()
    store: dict[tuple[str, int], DailyReviewResult] = {}
    prompts: list[str] = []

    async def _direct(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.pop("semaphore", None)
        return fn(*args, **kwargs)

    async def _fake_collect(target_date: date, *, use_realtime: bool) -> DailyReviewCollection:
        return _collection()

    async def _fake_run(spec: object, context: dict, **kwargs: object) -> PromptRun[DailyReviewPromptOutput]:
        prompts.append(str(context["prompt"]))
        await asyncio.sleep(0)
        return _prompt_run()

    async def _fake_resolve(requested_date: date | None, *, now: object = None) -> pipeline.DailyReviewDateResolution:
        return _historical_resolution()

    monkeypatch.setattr(pipeline, "call_blocking", _direct)
    monkeypatch.setattr(pipeline, "collect_daily_review_data", _fake_collect)
    monkeypatch.setattr(pipeline, "run_structured_prompt", _fake_run)
    monkeypatch.setattr(pipeline, "resolve_daily_review_date", _fake_resolve)
    monkeypatch.setattr(pipeline, "load_daily_review", lambda date_text, user_id: store.get((date_text, user_id)))
    monkeypatch.setattr(
        pipeline,
        "save_daily_review",
        lambda review, user_id: store.__setitem__((review.effective_date, user_id), review),
    )

    results = await asyncio.gather(
        pipeline.generate_daily_review(DailyReviewRequest(date=date(2026, 10, 14)), 7),
        pipeline.generate_daily_review(DailyReviewRequest(date=date(2026, 10, 14)), 8),
    )

    assert len(prompts) == 1
    assert sorted(store) == [("2026-10-14", 7), ("2026-10-14", 8)]
    assert {result.market_summary for result in results} == {"AI 摘要"}


# --- 政策新闻：按日期缓存搜索 + 只分类一次 ---

_POLICY_DATE = date(2026, 10, 14)


def _news_item(
    title: str = "央行降准 释放流动性",
    *,
    publish_time: str = "2026-10-14T09:30:00",
    url: str = "https://example.com/news/1",
) -> NewsSearchItem:
    return NewsSearchItem(
        title=title,
        content=f"{title}，政策内容说明",
        source="gov.cn",
        publish_time=publish_time,
        url=url,
        author="记者",
        read_count=0,
        comment_count=0,
    )


class _StubIndices:
    date = "2026-10-14"
    source = "stub"
    indices: list = []


async def test_policy_news_search_is_cached_per_date(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[date] = []

    async def _uncached(target_date: date) -> list[NewsSearchItem]:
        calls.append(target_date)
        return [_news_item()]

    monkeypatch.setattr(web_policy_news, "_search_financial_policy_news_uncached", _uncached)
    analysis_cache.clear()

    first = await web_policy_news.search_financial_policy_news(_POLICY_DATE)
    second = await web_policy_news.search_financial_policy_news(_POLICY_DATE)
    await web_policy_news.search_financial_policy_news(date(2026, 10, 13))

    assert [item.title for item in first] == ["央行降准 释放流动性"]
    assert second == first
    assert calls == [_POLICY_DATE, date(2026, 10, 13)]


async def test_empty_policy_news_result_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[date] = []

    async def _uncached(target_date: date) -> list[NewsSearchItem]:
        calls.append(target_date)
        return []

    monkeypatch.setattr(web_policy_news, "_search_financial_policy_news_uncached", _uncached)
    analysis_cache.clear()

    assert await web_policy_news.search_financial_policy_news(_POLICY_DATE) == []
    assert await web_policy_news.search_financial_policy_news(_POLICY_DATE) == []
    # 空结果（多为超时）不写缓存，允许下次重试。
    assert calls == [_POLICY_DATE, _POLICY_DATE]


async def _collect_with_news(
    monkeypatch: pytest.MonkeyPatch,
    *,
    local_news: list[NewsSearchItem],
    web_news: list[NewsSearchItem],
    classify: object | None = None,
) -> DailyReviewCollection:
    async def _empty(*args: object, **kwargs: object) -> list:
        return []

    async def _indices() -> _StubIndices:
        return _StubIndices()

    async def _news() -> list[NewsSearchItem]:
        return local_news

    async def _macro() -> MacroAnalysisResponse:
        return MacroAnalysisResponse(period="p", summary="", events=[], policy_signals=[])

    async def _web(target_date: date) -> list[NewsSearchItem]:
        return web_news

    monkeypatch.setattr(collector, "get_indices", _indices)
    monkeypatch.setattr(collector, "get_hot_stocks", _empty)
    monkeypatch.setattr(collector, "get_ths_hot_concept", _empty)
    monkeypatch.setattr(collector, "get_ths_hot_industry", _empty)
    monkeypatch.setattr(collector, "get_dragon_tiger_list", _empty)
    monkeypatch.setattr(collector, "get_market_statistics", _empty)
    monkeypatch.setattr(collector, "get_market_news", _news)
    monkeypatch.setattr(collector, "get_market_volume_stats", _empty)
    monkeypatch.setattr(collector, "get_macro_data", _empty)
    monkeypatch.setattr(collector, "get_macro_analysis", _macro)
    monkeypatch.setattr(collector, "get_limit_up_ladder", _empty)
    monkeypatch.setattr(collector, "_target_northbound", _empty)
    monkeypatch.setattr(collector, "search_financial_policy_news", _web)
    if classify is not None:
        monkeypatch.setattr(collector, "classify_policy_news", classify)
    return await collector.collect_daily_review_data(_POLICY_DATE, use_realtime=True)


async def test_collect_classifies_policy_news_once_without_web_news(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    real_classify = news_policy.classify_policy_news

    def _spy(items: object, **kwargs: object) -> list[PolicyNewsSnapshotItem]:
        materialized = list(items)  # type: ignore[call-overload]
        calls.append(len(materialized))
        return real_classify(materialized, **kwargs)  # type: ignore[arg-type]

    collection = await _collect_with_news(
        monkeypatch,
        local_news=[_news_item(), _news_item(title="证监会 发布新规", url="https://example.com/news/2")],
        web_news=[],
        classify=_spy,
    )

    # 上游合并 Web Search 结果但没有新增条目时，不应重复分类。
    assert calls == [2]
    assert [item.title for item in collection.policy_news] == ["央行降准 释放流动性", "证监会 发布新规"]


async def test_collect_reclassifies_after_merging_web_news(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    real_classify = news_policy.classify_policy_news

    def _spy(items: object, **kwargs: object) -> list[PolicyNewsSnapshotItem]:
        materialized = list(items)  # type: ignore[call-overload]
        calls.append(len(materialized))
        return real_classify(materialized, **kwargs)  # type: ignore[arg-type]

    collection = await _collect_with_news(
        monkeypatch,
        local_news=[_news_item()],
        web_news=[_news_item(title="国常会部署稳增长", url="https://example.com/news/3")],
        classify=_spy,
    )

    # 合并 Web Search 结果后必须重新分类，新增政策事件才会进入快照。
    assert calls == [1, 2]
    assert "国常会部署稳增长" in [item.title for item in collection.policy_news]


def test_build_snapshot_reuses_provided_policy_news(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args: object, **kwargs: object) -> list:
        raise AssertionError("build_snapshot 不应重复分类政策新闻")

    monkeypatch.setattr(review_builder, "classify_policy_news", _boom)
    provided = [PolicyNewsSnapshotItem(title="央行降准 释放流动性", event_type="policy")]

    snapshot = review_builder.build_snapshot(
        None, None, None, None, None, None, [_news_item()], None, None, policy_news=provided
    )

    assert [item.title for item in snapshot.policy_news] == ["央行降准 释放流动性"]


def test_build_snapshot_classifies_when_policy_news_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    real_classify = review_builder.classify_policy_news

    def _spy(items: object, **kwargs: object) -> list[PolicyNewsSnapshotItem]:
        calls.append(1)
        return real_classify(items, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(review_builder, "classify_policy_news", _spy)

    snapshot = review_builder.build_snapshot(
        None, None, None, None, None, None, [_news_item()], None, None, effective_date="2026-10-14"
    )

    assert len(calls) == 1
    assert [item.title for item in snapshot.policy_news] == ["央行降准 释放流动性"]


async def _patch_generation(
    monkeypatch: pytest.MonkeyPatch,
    store: dict[tuple[str, int], DailyReviewResult],
) -> None:
    async def _direct(fn: object, *args: object, **kwargs: object) -> object:
        kwargs.pop("semaphore", None)
        return fn(*args, **kwargs)  # type: ignore[operator]

    async def _fake_collect(target_date: date, *, use_realtime: bool) -> DailyReviewCollection:
        return _collection()

    async def _fake_run(spec: object, context: dict, **kwargs: object) -> PromptRun[DailyReviewPromptOutput]:
        return _prompt_run()

    async def _fake_resolve(requested_date: date | None, *, now: object = None) -> pipeline.DailyReviewDateResolution:
        return _historical_resolution()

    monkeypatch.setattr(pipeline, "call_blocking", _direct)
    monkeypatch.setattr(pipeline, "collect_daily_review_data", _fake_collect)
    monkeypatch.setattr(pipeline, "run_structured_prompt", _fake_run)
    monkeypatch.setattr(pipeline, "resolve_daily_review_date", _fake_resolve)
    monkeypatch.setattr(pipeline, "load_daily_review", lambda date_text, user_id: store.get((date_text, user_id)))
    monkeypatch.setattr(
        pipeline,
        "save_daily_review",
        lambda review, user_id: store.__setitem__((review.effective_date, user_id), review),
    )


async def test_generate_daily_review_reports_progress_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis_cache.clear()
    pipeline._generation_locks.clear()
    store: dict[tuple[str, int], DailyReviewResult] = {}
    events: list[dict] = []

    async def _record(event: dict) -> None:
        events.append(event)

    await _patch_generation(monkeypatch, store)

    await pipeline.generate_daily_review(
        DailyReviewRequest(date=date(2026, 10, 14)), 7, progress_callback=_record
    )

    assert [event["stage"] for event in events] == ["queue", "collect", "analyze", "persist"]
    assert all(event["type"] == "stage_started" for event in events)
    assert all(event["message"] for event in events)

    # 命中缓存时不再采集/生成，只回报排队阶段（前端仍由 complete 事件收尾）。
    events.clear()
    await pipeline.generate_daily_review(
        DailyReviewRequest(date=date(2026, 10, 14)), 7, progress_callback=_record
    )

    assert [event["stage"] for event in events] == ["queue"]


async def test_generate_daily_review_without_callback_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis_cache.clear()
    pipeline._generation_locks.clear()
    store: dict[tuple[str, int], DailyReviewResult] = {}

    await _patch_generation(monkeypatch, store)

    review = await pipeline.generate_daily_review(DailyReviewRequest(date=date(2026, 10, 14)), 7)

    assert review.market_summary == "AI 摘要"


def test_workflow_worker_forwards_progress_for_daily_review() -> None:
    """阶段事件由管线回报：Workflow 只负责把 progress_callback 透传给生成入口。"""
    source = inspect.getsource(workflow_worker.process_next_workflow_job)
    branch = source.split('elif job.kind == "daily_review":')[1].split("else:")[0]

    assert "progress_callback=emit" in branch
    assert "stage_started" not in branch


async def test_prewarm_daily_review_warms_shared_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis_cache.clear()
    prompts: list[str] = []
    resolutions: list[date | None] = []

    async def _fake_collect(target_date: date, *, use_realtime: bool) -> DailyReviewCollection:
        assert use_realtime is True
        return _collection()

    async def _fake_run(spec: object, context: dict, **kwargs: object) -> PromptRun[DailyReviewPromptOutput]:
        prompts.append(str(context["prompt"]))
        return _prompt_run()

    async def _fake_resolve(requested_date: date | None, *, now: object = None) -> pipeline.DailyReviewDateResolution:
        resolutions.append(requested_date)
        return pipeline.DailyReviewDateResolution(
            requested_date=date(2026, 10, 15),
            effective_date=date(2026, 10, 15),
            session_status="completed",
            use_realtime=True,
        )

    monkeypatch.setattr(pipeline, "collect_daily_review_data", _fake_collect)
    monkeypatch.setattr(pipeline, "run_structured_prompt", _fake_run)
    monkeypatch.setattr(pipeline, "resolve_daily_review_date", _fake_resolve)
    monkeypatch.setattr(pipeline, "get_effective_settings", lambda: Settings())

    assert await pipeline.prewarm_daily_review() is True
    assert len(prompts) == 1

    # 缓存已就绪：不再调用模型，只做一次采集快照命中。
    assert await pipeline.prewarm_daily_review() is False
    assert len(prompts) == 1
    assert resolutions == [None, None]


async def test_prewarm_daily_review_skips_when_session_not_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis_cache.clear()
    collected: list[str] = []

    async def _fake_collect(target_date: date, *, use_realtime: bool) -> DailyReviewCollection:
        collected.append(target_date.isoformat())
        return _collection()

    async def _fake_resolve(requested_date: date | None, *, now: object = None) -> pipeline.DailyReviewDateResolution:
        return _historical_resolution()

    monkeypatch.setattr(pipeline, "collect_daily_review_data", _fake_collect)
    monkeypatch.setattr(pipeline, "resolve_daily_review_date", _fake_resolve)

    assert await pipeline.prewarm_daily_review() is False
    assert collected == []


async def test_prewarm_daily_review_swallows_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis_cache.clear()

    async def _fake_collect(target_date: date, *, use_realtime: bool) -> DailyReviewCollection:
        return _collection()

    async def _fake_run(spec: object, context: dict, **kwargs: object) -> PromptRun[DailyReviewPromptOutput]:
        raise RuntimeError("模型不可用")

    async def _fake_resolve(requested_date: date | None, *, now: object = None) -> pipeline.DailyReviewDateResolution:
        return pipeline.DailyReviewDateResolution(
            requested_date=date(2026, 10, 15),
            effective_date=date(2026, 10, 15),
            session_status="completed",
            use_realtime=True,
        )

    monkeypatch.setattr(pipeline, "collect_daily_review_data", _fake_collect)
    monkeypatch.setattr(pipeline, "run_structured_prompt", _fake_run)
    monkeypatch.setattr(pipeline, "resolve_daily_review_date", _fake_resolve)
    monkeypatch.setattr(pipeline, "get_effective_settings", lambda: Settings())

    # 后台任务不得因单次 LLM 失败而抛出。
    assert await pipeline.prewarm_daily_review() is False


def test_lifecycle_registers_daily_review_prewarm() -> None:
    import inspect as _inspect

    from app.runtime import lifecycle

    assert "daily_review_prewarm" in _inspect.getsource(lifecycle.build_background_task_specs)
    assert "daily_review_prewarm=daily_review_prewarm" in _inspect.getsource(lifecycle.application_lifespan)


async def test_settled_realtime_snapshot_uses_long_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis_cache.clear()
    recorded: list[float] = []
    original_set = analysis_cache.set

    def _spy(key: str, value: object, ttl: float) -> None:
        recorded.append(ttl)
        original_set(key, value, ttl)

    async def _fake_collect(target_date: date, *, use_realtime: bool) -> DailyReviewCollection:
        return _collection()

    monkeypatch.setattr(analysis_cache, "set", _spy)
    monkeypatch.setattr(pipeline, "collect_daily_review_data", _fake_collect)

    realtime_resolution = pipeline.DailyReviewDateResolution(
        requested_date=date(2026, 10, 15),
        effective_date=date(2026, 10, 15),
        session_status="completed",
        use_realtime=True,
    )

    await pipeline._collect_shared(realtime_resolution)
    await pipeline._collect_shared(_historical_resolution())

    assert recorded == [
        pipeline._SETTLED_COLLECTION_CACHE_TTL_SECONDS,
        pipeline._COLLECTION_CACHE_TTL_SECONDS,
    ]


async def test_generate_daily_review_maps_deep_fields_and_grounds_watchlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_cache.clear()
    pipeline._generation_locks.clear()
    store: dict[tuple[str, int], DailyReviewResult] = {}
    await _patch_generation(monkeypatch, store)

    deep = _prompt_run().value.model_copy(
        update={
            "next_day_watchlist": [DailyReviewWatchItem(name="虚构股", role="总龙头")],
            "key_levels": ["上证 3250 支撑"],
        }
    )

    async def _fake_run(spec: object, context: dict, **kwargs: object) -> PromptRun[DailyReviewPromptOutput]:
        base = _prompt_run()
        return PromptRun(value=deep, trace=base.trace)

    monkeypatch.setattr(pipeline, "run_structured_prompt", _fake_run)

    review = await pipeline.generate_daily_review(DailyReviewRequest(date=date(2026, 10, 14)), 7)

    assert review.sentiment_cycle is not None
    assert review.sentiment_cycle.stage == "主升共振"
    assert [scenario.name for scenario in review.scenario_plans] == ["超预期", "符合预期", "低于预期"]
    assert review.key_levels == ["上证 3250 支撑"]
    # 快照里不存在的个股必须被丢弃，不允许虚构观察标的（此处快照无涨停天梯，因此回退为空）。
    assert review.next_day_watchlist == []


async def test_review_history_reads_trend_only_before_effective_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """历史趋势必须排除当日：否则写入当日摘要会改变当日 Prompt，预热与共享缓存全部失效。"""
    calls: list[tuple[int, str | None]] = []

    def _recent(limit: int, *, before: str | None = None) -> list[DailyReviewCycleRecord]:
        calls.append((limit, before))
        return []

    monkeypatch.setattr(pipeline, "previous_cycle_record", lambda date_text: None)
    monkeypatch.setattr(pipeline, "recent_cycle_records", _recent)

    check, trend = await pipeline._review_history_inputs(
        "2026-10-14",
        _historical_resolution(),
        DailyReviewDataSnapshot(),
    )

    assert check is None
    assert trend.points == []
    assert calls == [(pipeline._CYCLE_TREND_DAYS, "2026-10-14")]


async def test_generate_daily_review_embeds_history_and_writes_cycle_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_cache.clear()
    pipeline._generation_locks.clear()
    store: dict[tuple[str, int], DailyReviewResult] = {}
    saved: list[DailyReviewCycleRecord] = []
    await _patch_generation(monkeypatch, store)
    monkeypatch.setattr(pipeline, "save_cycle_record", saved.append)
    monkeypatch.setattr(
        pipeline,
        "previous_cycle_record",
        lambda date_text: DailyReviewCycleRecord(date="2026-10-13", stage="冰点", limit_up_count=61),
    )
    monkeypatch.setattr(
        pipeline,
        "recent_cycle_records",
        lambda limit, **kwargs: [DailyReviewCycleRecord(date="2026-10-13", stage="冰点", limit_up_count=61)],
    )

    review = await pipeline.generate_daily_review(DailyReviewRequest(date=date(2026, 10, 14)), 7)

    # 上一交易日自检：快照无观察标的，但阶段与涨停家数变化仍必须落到结果与 Markdown。
    assert review.previous_review_check is not None
    assert review.previous_review_check.review_date == "2026-10-13"
    assert review.previous_review_check.previous_stage == "冰点"
    assert [point.date for point in review.cycle_trend.points] == ["2026-10-13"]
    assert "## 上一交易日复盘自检（2026-10-13 → 2026-10-14）" in review.llm_review
    assert "## 情绪周期历史趋势" in review.llm_review

    # 当日摘要写入全局表：次日复盘的闭环与趋势都由它提供。
    assert [record.date for record in saved] == ["2026-10-14"]
    assert saved[0].stage == "主升共振"
