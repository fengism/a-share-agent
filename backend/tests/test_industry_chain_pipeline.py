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
    ctx.before_persist = None
    ctx.result = IndustryChainResult(name="测试产业", summary="初稿摘要")
    ctx.warnings = ["提示警告"]
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
