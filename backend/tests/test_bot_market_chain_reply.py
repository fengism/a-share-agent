"""Bot /market 与 /chain 命令回复的守卫测试。"""

from app.modules.bot.commands.chain import ChainCommand, _format_chain_reply
from app.modules.bot.commands.market import MarketCommand, _data_section_text, _format_market_reply
from app.modules.bot.models import BotResponse
from app.modules.daily_review.models import DailyReviewDataSnapshot, DailyReviewResult, DailyReviewSection


def _make_snapshot() -> DailyReviewDataSnapshot:
    return DailyReviewDataSnapshot(
        indices=[{"name": "上证指数", "price": 3300.5, "change_pct": 0.65}],
        market_volume={
            "date": "2026-09-25",
            "amount": 1.65e12,
            "amount_before_one_day": 1.75e12,
            "amount_average_20_day": 1.85e12,
            "amount_average_60_day": 2.25e12,
        },
        limit_up_ladder={"stocks": [{"name": "空间龙", "board_count": 6, "sector_name": "算力"}]},
        northbound_funds={"north_money": 42.1},
        top_sectors=[{"name": "算力", "change_pct": 3.2, "leading_stock": "中际旭创"}],
    )


def _make_review(snapshot: DailyReviewDataSnapshot | None = None, **overrides) -> DailyReviewResult:
    fields = dict(
        date="2026-09-25",
        effective_date="2026-09-25",
        title="每日复盘",
        generated_at="2026-09-25 16:00:00",
        market_state="balanced",
        position_range="4-6 成",
        market_summary="市场震荡整理，量能小幅萎缩。" * 3,
        index_review=DailyReviewSection(title="指数", summary="震荡", bullets=[]),
        hotspot_review=DailyReviewSection(title="热点", summary="轮动", bullets=[]),
        dragon_tiger_review=DailyReviewSection(title="龙虎榜", summary="活跃", bullets=[]),
        opportunities=["算力主线扩散", "出海链修复"],
        risk_alerts=["高位股分歧加大"],
        data_snapshot=snapshot if snapshot is not None else _make_snapshot(),
    )
    fields.update(overrides)
    return DailyReviewResult(**fields)


def test_format_market_reply_contains_conclusion_and_data_digest():
    text = _format_market_reply(_make_review())
    assert "2026-09-25 市场复盘" in text
    assert "均衡" in text and "4-6 成" in text
    assert "机会方向" in text and "算力主线扩散" in text
    assert "风险提示" in text and "高位股分歧加大" in text
    # 数据看板复用推送内容块：成交额均线、连板天梯、北向资金
    assert "📊 数据看板" in text
    assert "20日均值" in text
    assert "空间龙" in text
    assert "北向资金净买入" in text


def test_format_market_reply_trims_long_summary():
    review = _make_review(market_summary="超长摘要" * 500)
    text = _format_market_reply(review)
    assert "…" in text
    assert len(text) < 4000


def test_data_section_text_only_keeps_selected_headings():
    text = _data_section_text(_make_snapshot(), char_budget=2000)
    assert "主要指数表现" in text
    assert "量能与市场宽度" in text
    assert "短线连板天梯" in text
    # 没有出现未选择的数据段（如龙虎榜）
    assert "龙虎榜" not in text


async def test_market_execute_reports_progress_and_replies(monkeypatch):
    from unittest.mock import AsyncMock

    progress: list[BotResponse] = []

    class _Context:
        service_user_id = 1

        async def report_progress(self, response: BotResponse) -> None:
            progress.append(response)

    generated = _make_review(snapshot=None)
    monkeypatch.setattr(
        "app.modules.bot.commands.market.generate_daily_review",
        AsyncMock(return_value=generated),
    )

    response = await MarketCommand().execute(None, [], _Context())

    assert len(progress) == 1
    assert "正在获取当日复盘" in progress[0].text
    assert "市场复盘" in response.title
    assert "机会方向" in response.text


def _make_chain_result() -> object:
    from app.modules.industry_chain.models import (
        IndustryChainNode,
        IndustryChainOpportunity,
        IndustryChainResult,
        IndustryChainThesis,
    )

    return IndustryChainResult(
        name="光模块",
        positioning="AI 算力网络核心器件环节",
        research_theses=[
            IndustryChainThesis(
                title="800G 升级带动量价齐升",
                detail="海外云厂商资本开支上行，800G 出货占比快速提升，龙头业绩确定性高。",
            ),
        ],
        opportunities=[
            IndustryChainOpportunity(name="光引擎", code="300308", role="中游制造", total_score=86),
            IndustryChainOpportunity(name="陶瓷外壳", role="上游材料", total_score=71),
        ],
        risks=["行业竞争加剧", "技术路线切换"],
        key_stocks=[
            IndustryChainNode(name="中际旭创", code="300308", role="光模块龙头"),
            IndustryChainNode(name="新易盛", code="300502"),
        ],
    )


def test_format_chain_reply_contains_all_sections():
    text = _format_chain_reply(_make_chain_result())
    assert "光模块" in text and "产业链定位" in text and "AI 算力网络核心器件环节" in text
    assert "核心研究论点" in text and "800G 升级带动量价齐升" in text
    assert "机会方向" in text and "光引擎 300308" in text and "综合 86" in text
    assert "风险提示" in text and "行业竞争加剧" in text
    assert "关键公司" in text and "中际旭创（300308）" in text and "新易盛（300502）" in text


async def test_chain_execute_loads_latest_archive(monkeypatch):
    from unittest.mock import AsyncMock, Mock

    from app.modules.industry_chain.public import IndustryChainLatestResponse

    monkeypatch.setattr(
        "app.modules.bot.commands.chain.get_latest_industry_chain_archive",
        AsyncMock(return_value=IndustryChainLatestResponse(archive_id="arch-1", saved_at="2026-09-26")),
    )
    load_mock = Mock(return_value=_make_chain_result())
    monkeypatch.setattr("app.modules.bot.commands.chain.load_industry_chain", load_mock)

    class _Context:
        service_user_id = 1

    response = await ChainCommand().execute(None, ["光模块"], _Context())

    assert response.title == "产业链分析 · 光模块"
    assert "核心研究论点" in response.text
    # 同步读取经 call_blocking 进线程池，参数原样透传
    assert load_mock.call_args.args == ("光模块", "arch-1", 1)


async def test_chain_execute_prompts_when_no_archive(monkeypatch):
    from unittest.mock import AsyncMock

    from app.modules.industry_chain.public import IndustryChainLatestResponse

    monkeypatch.setattr(
        "app.modules.bot.commands.chain.get_latest_industry_chain_archive",
        AsyncMock(return_value=IndustryChainLatestResponse(archive_id="")),
    )

    class _Context:
        service_user_id = 1

    response = await ChainCommand().execute(None, ["不存在的行业"], _Context())
    assert "存档" in response.text
    assert "网页端生成" in response.text
