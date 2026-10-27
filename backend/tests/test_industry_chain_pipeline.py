import pytest

from app.modules.industry_chain.enrichment import (
    enrich_result_stock_codes,
    enrich_stock_market_snapshots,
    find_stock_code_from_text,
    format_market_cap,
)
from app.modules.industry_chain.models import (
    IndustryChainNode,
    IndustryChainResult,
)
from app.modules.industry_chain.pipeline_context import PipelineContext


def test_format_market_cap():
    assert format_market_cap(0) == ""
    assert format_market_cap(-100) == ""
    assert format_market_cap(50_000_000_000) == "500.0亿"
    assert format_market_cap(350_000) == "35.0万"
    assert format_market_cap(800) == "800"


def test_find_stock_code_from_text():
    mapping = {
        "宁德时代": "300750",
        "比亚迪": "002594",
        "中芯国际": "688981",
    }
    assert find_stock_code_from_text("", mapping) == ""
    assert find_stock_code_from_text("宁德时代", mapping) == "300750"
    assert find_stock_code_from_text("动力电池龙头宁德时代新能源", mapping) == "300750"
    assert find_stock_code_from_text("未知公司ABC", mapping) == ""


def test_enrich_result_stock_codes():
    result = IndustryChainResult(
        name="动力电池",
        upstream=[IndustryChainNode(name="正极材料", companies=["宁德时代", "未知小厂"])],
        key_stocks=[
            IndustryChainNode(name="宁德时代", code=""),
            IndustryChainNode(name="比亚迪", code="002594"),
        ],
    )
    # name_map is standard code -> name
    code_to_name = {
        "300750": "宁德时代",
        "002594": "比亚迪",
    }
    enriched = enrich_result_stock_codes(result, code_to_name)
    # Check that key_stocks empty code was filled
    assert enriched.key_stocks[0].code == "300750"
    assert enriched.key_stocks[1].code == "002594"


def test_enrich_stock_market_snapshots():
    result = IndustryChainResult(
        name="动力电池",
        key_stocks=[
            IndustryChainNode(name="宁德时代", code="300750"),
        ],
    )
    snapshots = {
        "300750": {
            "pe": "25.4x",
            "pb": "4.10",
            "total_market_cap": "8500.0亿",
        }
    }
    enriched = enrich_stock_market_snapshots(result, snapshots)
    stock = enriched.key_stocks[0]
    assert stock.pe == "25.4x"
    assert stock.pb == "4.10"
    assert stock.total_market_cap == "8500.0亿"


def test_pipeline_context_events():
    from app.core.progress import ProgressEmitter
    from app.domain.industry_chain import IndustryChainResearchScope

    ctx = PipelineContext(
        name="光伏设备",
        user_id=1,
        resolved_scope=IndustryChainResearchScope(),
        settings=None,  # type: ignore
        progress=ProgressEmitter(),
    )
    event = ctx.make_event(
        event_type="stage_started",
        stage="research",
        message="调研开始",
    )
    assert event.type == "stage_started"
    assert event.stage == "research"
    assert event.message == "调研开始"


@pytest.mark.asyncio
async def test_execute_finalize_stage():
    from app.core.progress import ProgressEmitter
    from app.domain.industry_chain import IndustryChainResearchScope
    from app.modules.industry_chain.pipeline_stages import execute_finalize_stage

    emitted = []

    async def mock_handler(event):
        emitted.append(event)

    emitter = ProgressEmitter(callback=mock_handler)

    ctx = PipelineContext(
        name="动力电池",
        user_id=1,
        resolved_scope=IndustryChainResearchScope(),
        settings=None,  # type: ignore
        progress=emitter,
    )
    ctx.result = IndustryChainResult(
        name="动力电池",
        summary="动力电池分析",
        upstream=[IndustryChainNode(name="正极材料", companies=["宁德时代"])],
        key_stocks=[IndustryChainNode(name="宁德时代", code="300750")],
    )
    ctx.structured_prompt_succeeded = True

    await execute_finalize_stage(ctx)

    assert len(ctx.result.charts) > 0
    assert ctx.result.analysis_metadata is not None
    assert ctx.finalization_duration_ms >= 0
    assert len(emitted) == 2
    assert emitted[0].type == "stage_started"
    assert emitted[0].stage == "finalize"
    assert emitted[1].type == "stage_completed"
    assert emitted[1].stage == "finalize"
    assert emitted[1].result is not None


def test_enrich_stock_market_snapshots_all_tiers_and_refresh():
    from app.modules.industry_chain.models import IndustryChainCompetitionGroup

    result = IndustryChainResult(
        name="动力电池",
        upstream=[IndustryChainNode(name="锂矿", code="002460", pe="10.0x")],
        midstream=[IndustryChainNode(name="电芯", code="300750")],
        downstream=[IndustryChainNode(name="整车", code="002594")],
        competition=[
            IndustryChainCompetitionGroup(
                market="国内动力电池",
                companies=[IndustryChainNode(name="中创新航", code="300750")],
            )
        ],
        key_stocks=[
            IndustryChainNode(name="宁德时代", code="300750", pe="20.0x"),
        ],
    )
    snapshots = {
        "002460": {"pe": "12.5x", "pb": "2.10", "total_market_cap": "800.0亿"},
        "300750": {"pe": "25.4x", "pb": "4.10", "total_market_cap": "8500.0亿"},
        "002594": {"pe": "22.0x", "pb": "3.80", "total_market_cap": "7000.0亿"},
    }

    # Case 1: Without refresh_existing, existing pe (20.0x) is preserved
    enriched = enrich_stock_market_snapshots(result, snapshots, refresh_existing=False)
    assert enriched.key_stocks[0].pe == "20.0x"
    assert enriched.key_stocks[0].total_market_cap == "8500.0亿"
    assert enriched.upstream[0].pe == "10.0x"
    assert enriched.upstream[0].total_market_cap == "800.0亿"
    assert enriched.midstream[0].pe == "25.4x"
    assert enriched.downstream[0].pe == "22.0x"
    assert enriched.competition[0].companies[0].total_market_cap == "8500.0亿"

    # Case 2: With refresh_existing, latest market snapshot overwrites old values
    refreshed = enrich_stock_market_snapshots(result, snapshots, refresh_existing=True)
    assert refreshed.key_stocks[0].pe == "25.4x"
    assert refreshed.upstream[0].pe == "12.5x"


@pytest.mark.asyncio
async def test_pipeline_context_cancellation_and_checkpoint():
    import asyncio

    from app.core.progress import ProgressEmitter
    from app.domain.industry_chain import IndustryChainResearchScope

    ctx = PipelineContext(
        name="测试产业",
        user_id=999,
        resolved_scope=IndustryChainResearchScope(),
        settings=None,  # type: ignore
        progress=ProgressEmitter(),
    )

    # 正常无取消状态下运行
    await ctx.check_cancellation()

    # 模拟外部状态回调抛出取消
    async def cancelled_callback():
        raise asyncio.CancelledError("外部取消")

    ctx.before_persist = cancelled_callback
    with pytest.raises(asyncio.CancelledError):
        await ctx.check_cancellation()

    # 检查点保存与加载
    from app.agentic.contracts import AgentEvidence

    ctx.before_persist = None
    ctx.result = IndustryChainResult(name="测试产业", summary="初稿摘要")
    ctx.warnings = ["提示警告"]
    ctx.all_evidence = [
        AgentEvidence(
            tool_call_id="call_1",
            tool_name="web_search",
            arguments='{"query": "测试"}',
            content='{"result": "有效证据"}',
        )
    ]
    ctx.prompt_context = {"test_key": "test_val"}
    ctx.save_checkpoint("draft")

    restored_ctx = PipelineContext(
        name="测试产业",
        user_id=999,
        resolved_scope=IndustryChainResearchScope(),
        settings=None,  # type: ignore
        progress=ProgressEmitter(),
    )
    loaded = restored_ctx.load_checkpoint("draft")
    assert loaded is True
    assert restored_ctx.result is not None
    assert restored_ctx.result.summary == "初稿摘要"
    assert "提示警告" in restored_ctx.warnings
    assert len(restored_ctx.all_evidence) == 1
    assert restored_ctx.all_evidence[0].tool_call_id == "call_1"
    assert len(restored_ctx.evidence_catalog) >= 1
    assert restored_ctx.prompt_context == {"test_key": "test_val"}


def test_build_node_adjacency_map():
    from app.modules.industry_chain.models import IndustryChainRelationship
    from app.modules.industry_chain.relationships import build_node_adjacency_map

    result = IndustryChainResult(
        name="动力电池",
        relationships=[
            IndustryChainRelationship(
                source_node="天齐锂业",
                target_node="宁德时代",
                relation_type="supply",
                title="碳酸锂供应",
            ),
            IndustryChainRelationship(
                source_node="宁德时代",
                target_node="比亚迪",
                relation_type="compete",
                title="电池竞争",
            ),
        ],
    )
    adjacency = build_node_adjacency_map(result)
    assert "宁德时代" in adjacency
    assert "天齐锂业" in adjacency["宁德时代"]["upstream"]
    assert "宁德时代" in adjacency["天齐锂业"]["downstream"]
    assert "比亚迪" in adjacency["宁德时代"]["compete"]
    assert "宁德时代" in adjacency["比亚迪"]["compete"]


@pytest.mark.asyncio
async def test_run_pipeline_resume_from_checkpoint(monkeypatch):
    from app.core.progress import ProgressEmitter
    from app.modules.industry_chain.pipeline import run_industry_chain_analysis

    # 预存一个 verification 检查点
    ctx = PipelineContext(
        name="测试恢复链",
        user_id=1001,
        resolved_scope=None,  # type: ignore
        settings=None,  # type: ignore
        progress=ProgressEmitter(),
    )
    ctx.result = IndustryChainResult(
        name="测试恢复链",
        summary="核验后的初稿",
        upstream=[IndustryChainNode(name="上游材料", code="002460")],
        key_stocks=[IndustryChainNode(name="标的一", code="002460")],
    )
    ctx.save_checkpoint("verification")

    events = []

    async def callback(event):
        events.append(event)

    # 尝试断点恢复执行，mock call_blocking 和 background task 避免真实 DB 交互
    monkeypatch.setattr(
        "app.modules.industry_chain.pipeline_stages.call_blocking",
        lambda *args, **kwargs: "mock_archive_id_123",
    )
    monkeypatch.setattr(
        "app.modules.industry_chain.pipeline_stages.get_latest_industry_chain_archive",
        lambda *args, **kwargs: IndustryChainResult(name="测试恢复链"),
    )

    resumed_result = await run_industry_chain_analysis(
        name="测试恢复链",
        user_id=1001,
        progress_callback=callback,
        force=False,
        resume_from_checkpoint=True,
    )
    assert resumed_result is not None
    assert resumed_result.summary == "核验后的初稿"
    stages_called = [e.stage for e in events]
    assert "checkpoint_resumed" in stages_called
    assert "research" not in stages_called


def test_compute_industry_chain_changes_fuzzy_alignment():
    from app.modules.industry_chain.diff import compute_industry_chain_changes
    from app.modules.industry_chain.models import IndustryChainNode, IndustryChainResult

    scope = {"region": "china", "company_scope": "a_share", "time_range": "one_year"}
    prev_result = IndustryChainResult(
        name="动力电池",
        research_scope=scope,
        upstream=[IndustryChainNode(name="正极材料", role="提供正极活性物质")],
    )
    curr_result = IndustryChainResult(
        name="动力电池",
        research_scope=scope,
        upstream=[IndustryChainNode(name="锂电正极材料", role="提供高镍/磷酸铁锂正极材料")],
    )
    change_set = compute_industry_chain_changes(prev_result, curr_result)
    assert change_set.comparable is True
    assert change_set.has_changes is True
    # 模糊对齐应当将其判定为 updated 而非 1 个 added + 1 个 removed
    assert change_set.updated_count >= 1
    assert change_set.added_count == 0
    assert change_set.removed_count == 0
    updated_item = [item for item in change_set.items if item.category == "chain"][0]
    assert updated_item.change_type == "updated"
    assert "原表述" in updated_item.title or "原表述" in updated_item.detail


def test_compute_industry_chain_changes_with_value_dist_and_divergence():
    from app.modules.industry_chain.diff import compute_industry_chain_changes
    from app.modules.industry_chain.models import (
        IndustryChainExpectationDivergence,
        IndustryChainResult,
        IndustryChainValueDistribution,
    )

    scope = {"region": "china", "company_scope": "a_share", "time_range": "one_year"}
    prev_result = IndustryChainResult(
        name="人形机器人",
        research_scope=scope,
        value_distribution=[
            IndustryChainValueDistribution(
                segment="旋转执行器",
                cost_share="25%",
                gross_margin_range="40%~50%",
            ),
        ],
        expectation_divergences=[
            IndustryChainExpectationDivergence(
                topic="量产节奏",
                consensus="2025年内万台交付",
                divergence="预计延后至2026",
            ),
        ],
    )
    curr_result = IndustryChainResult(
        name="人形机器人",
        research_scope=scope,
        value_distribution=[
            IndustryChainValueDistribution(
                segment="旋转执行器",
                cost_share="28%",
                gross_margin_range="45%~55%",
            ),
        ],
        expectation_divergences=[
            IndustryChainExpectationDivergence(
                topic="量产节奏",
                consensus="2025年内万台交付",
                divergence="预计2025Q4提前达成定点",
            ),
        ],
    )
    change_set = compute_industry_chain_changes(prev_result, curr_result)
    assert change_set.has_changes is True
    val_items = [it for it in change_set.items if "价值链BOM" in it.title]
    assert len(val_items) == 1
    assert val_items[0].change_type == "updated"

    div_items = [it for it in change_set.items if "预期差" in it.title]
    assert len(div_items) == 1
    assert div_items[0].change_type == "updated"



async def test_enrich_stocks_financial_breakdown(monkeypatch):
    from unittest.mock import AsyncMock
    from app.financial_data.stock.fundamentals.schemas import RevenueBreakdown, RevenueBreakdownItem
    from app.modules.industry_chain.enrichment import enrich_stocks_financial_breakdown
    from app.modules.industry_chain.models import IndustryChainNode, IndustryChainResult

    mock_breakdown = RevenueBreakdown(
        code="002371",
        symbol="SZ002371",
        name="北方华创",
        by_product=[
            RevenueBreakdownItem(
                class_name="电子工艺装备",
                revenue_share_pct=82.5,
                gross_margin_pct=41.8,
            ),
            RevenueBreakdownItem(
                class_name="电子元器件",
                revenue_share_pct=17.5,
                gross_margin_pct=33.2,
            ),
        ],
        by_region=[
            RevenueBreakdownItem(
                class_name="境外",
                revenue_share_pct=11.2,
                gross_margin_pct=38.6,
            ),
            RevenueBreakdownItem(
                class_name="境内",
                revenue_share_pct=88.8,
                gross_margin_pct=42.1,
            ),
        ],
    )
    monkeypatch.setattr(
        "app.financial_data.stock.fundamentals.financials.get_revenue_breakdown",
        AsyncMock(return_value=mock_breakdown),
    )

    result = IndustryChainResult(
        name="半导体设备",
        key_stocks=[
            IndustryChainNode(
                code="002371",
                name="北方华创",
                role="刻蚀机龙头",
                # 未填写毛利率和收入占比
            ),
        ],
    )

    enriched = await enrich_stocks_financial_breakdown(result)
    target = enriched.key_stocks[0]
    assert target.gross_margin == "41.8%"
    assert "82.5%" in target.revenue_share
    assert "电子工艺装备" in target.revenue_share
    assert "11.2%" in target.overseas_share
    assert "境外" in target.overseas_share
    assert "毛利38.6%" in target.overseas_share


@pytest.mark.asyncio
async def test_enrich_macro_commodity_and_customs(monkeypatch):
    from unittest.mock import AsyncMock
    from app.modules.industry_chain.enrichment import enrich_macro_commodity_and_customs
    from app.modules.industry_chain.models import IndustryChainResult

    mock_commodity = AsyncMock(
        return_value={
            "status": "available",
            "items": [
                {
                    "name": "碳酸锂连续",
                    "latest_price": 76500.0,
                    "unit": "元/吨",
                    "change_pct": 2.35,
                    "date": "2026-10-24",
                    "status": "available",
                    "source": "新浪期货",
                    "source_url": "https://hq.sinajs.cn/list=nf_LC0",
                }
            ],
        }
    )
    mock_customs = AsyncMock(
        return_value={
            "latest_month_summary": {"month": "2026-09"},
            "matched_commodity_profiles": [
                {
                    "commodity": "锂离子蓄电池",
                    "trade_type": "出口",
                    "key_target_markets": "欧洲、北美、东南亚",
                }
            ],
        }
    )
    monkeypatch.setattr("app.financial_data.market.quotes.commodity.get_commodity_spot_prices", mock_commodity)
    monkeypatch.setattr("app.financial_data.market.quotes.customs.get_customs_trade_data", mock_customs)

    result = IndustryChainResult(name="锂电池")
    enriched = await enrich_macro_commodity_and_customs(result)
    labels = [m.label for m in enriched.market_metrics]
    assert "碳酸锂连续主力价" in labels
    assert "锂离子蓄电池出海跟踪" in labels
    metric = next(m for m in enriched.market_metrics if m.label == "碳酸锂连续主力价")
    assert "76500.0 元/吨" in metric.value
    assert "+2.35%" in metric.growth


def test_build_repair_targets_triggers_bear_and_depth_audit():
    from app.modules.industry_chain.models import IndustryChainNode, IndustryChainResult, IndustryChainThesis
    from app.modules.industry_chain.verification_repair import build_repair_targets

    # 初稿论点缺少 counter_evidence，且缺少 BOM 与预期差
    result = IndustryChainResult(
        name="商业航天",
        research_theses=[
            IndustryChainThesis(
                title="低轨星座组网加速推进",
                detail="国内民营火箭发射频次显著提升。",
                counter_evidence="",  # 空头证据缺失
                invalidation="",  # 失效条件缺失
            ),
        ],
        upstream=[IndustryChainNode(name="火箭发动机", role="动力总成")],
        midstream=[IndustryChainNode(name="运载火箭制造", role="箭体总装")],
        downstream=[IndustryChainNode(name="卫星互联网运营", role="空间宽带")],
        value_distribution=[],  # 缺少 BOM 拆解
        expectation_divergences=[],  # 缺少预期差
    )

    targets = build_repair_targets(result, [])
    target_keys = {t.key for t in targets}

    # 验证逆向/空头审计（Bear Audit）被成功激活
    assert "audit:bear" in target_keys
    bear_target = next(t for t in targets if t.key == "audit:bear")
    assert "逆向/空头审计" in bear_target.question
    assert "低轨星座组网加速推进" in bear_target.question

    # 验证价值链与预期差审计目标生成
    assert "audit:profit_pool" in target_keys or "audit:divergence" in target_keys


async def test_enrich_stocks_valuation_percentile_and_consensus_forecast(monkeypatch):
    from unittest.mock import AsyncMock
    from app.financial_data.stock.valuation.schemas import InstitutionForecast
    from app.modules.industry_chain.enrichment import (
        enrich_stocks_consensus_forecast,
        enrich_stocks_valuation_percentile,
    )
    from app.modules.industry_chain.models import IndustryChainNode, IndustryChainResult

    # Mock 估值百分位
    mock_compute_percentiles = AsyncMock(
        return_value=[{"code": "002371", "percentile": 16.5}]
    )
    monkeypatch.setattr(
        "app.financial_data.stock.valuation.percentiles.compute_percentiles",
        mock_compute_percentiles,
    )

    # Mock 机构一致预期
    mock_forecasts = [
        InstitutionForecast(
            metric="EPS",
            year="2025",
            institution_count=22.0,
            mean_value=2.45,
        ),
        InstitutionForecast(
            metric="PE",
            year="2025",
            institution_count=22.0,
            mean_value=25.2,
        ),
    ]
    monkeypatch.setattr(
        "app.financial_data.stock.valuation.detail._fetch_institution_forecasts",
        AsyncMock(return_value=mock_forecasts),
    )

    result = IndustryChainResult(
        name="半导体设备",
        key_stocks=[
            IndustryChainNode(
                code="002371",
                name="北方华创",
                pe="30.5",
            ),
        ],
    )

    # 1. 估值百分位富化
    res1 = await enrich_stocks_valuation_percentile(result)
    assert res1.key_stocks[0].pe_percentile == "16.5% (近三年低估)"

    # 2. 机构一致预期富化
    res2 = await enrich_stocks_consensus_forecast(res1)
    target = res2.key_stocks[0]
    assert "22家机构预测" in target.consensus_forecast
    assert "2025E EPS 2.45元" in target.consensus_forecast
    assert "PE 25.2倍" in target.consensus_forecast


@pytest.mark.asyncio
async def test_enrich_stocks_financial_metrics_and_restricted_risk(monkeypatch):
    from unittest.mock import AsyncMock
    from app.modules.industry_chain.enrichment import (
        enrich_stocks_financial_metrics,
        enrich_stocks_restricted_risk,
    )
    from app.financial_data.stock.fundamentals.schemas import FinancialMetrics

    mock_metrics = FinancialMetrics(
        code="002371",
        metrics={
            "净资产收益率": 0.185,
            "营收同比": 35.6,
            "净利润同比": 48.2,
        },
    )
    monkeypatch.setattr(
        "app.financial_data.stock.fundamentals.financials.get_financial_metrics",
        AsyncMock(return_value=mock_metrics),
    )

    mock_lift = {
        "has_upcoming_lifts": True,
        "total_upcoming_ratio_float_pct": 3.2,
        "pressure_risk_assessment": "未来存在一定限售股抛压",
    }
    monkeypatch.setattr(
        "app.financial_data.stock.insights.restricted.get_restricted_shares_lift",
        AsyncMock(return_value=mock_lift),
    )

    result = IndustryChainResult(
        name="半导体设备",
        key_stocks=[
            IndustryChainNode(
                code="002371",
                name="北方华创",
            ),
        ],
    )

    res1 = await enrich_stocks_financial_metrics(result)
    assert res1.key_stocks[0].roe == "18.5%"
    assert res1.key_stocks[0].growth_rate == "营收+35.6% / 净利+48.2%"

    res2 = await enrich_stocks_restricted_risk(res1)
    assert "近6个月预计解禁占流通盘 3.2%" in res2.key_stocks[0].restricted_risk


def test_build_industry_charts_with_value_distribution_and_matrix():
    from app.modules.industry_chain.charts import build_industry_charts
    from app.modules.industry_chain.models import IndustryChainValueDistribution

    result = IndustryChainResult(
        name="机器人",
        upstream=[IndustryChainNode(name="减速器", company="绿的谐波")],
        value_distribution=[
            IndustryChainValueDistribution(
                segment="减速器",
                cost_share="35%",
                gross_margin_range="40%~50%",
                pricing_power="high",
            ),
            IndustryChainValueDistribution(
                segment="伺服电机",
                cost_share="25%",
                gross_margin_range="30%~35%",
                pricing_power="medium",
            ),
        ],
        key_stocks=[
            IndustryChainNode(
                name="绿的谐波",
                code="688017",
                pe="45.2",
                roe="14.8%",
                total_market_cap="180.5亿",
                overseas_share="22.5% (海外业务)",
            ),
            IndustryChainNode(
                name="汇川技术",
                code="300124",
                pe="28.4",
                roe="19.2%",
                total_market_cap="1650.0亿",
                overseas_share="18.6% (外销)",
            ),
        ],
    )
    charts = build_industry_charts(result)
    assert len(charts) == 4
    assert "全景图谱" in charts[0].title
    assert "价值链 BOM" in charts[1].title
    assert charts[1].type == "bar"
    assert "估值与资本回报象限图" in charts[2].title
    assert charts[2].type == "scatter"
    assert "出海敞口对比" in charts[3].title
    assert charts[3].type == "bar"





