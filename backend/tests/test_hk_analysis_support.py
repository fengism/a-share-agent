"""港股分析分流：市场识别、工具集、Prompt 标注、关键点位与落盘路径。"""

import re
from unittest.mock import AsyncMock, patch

import pytest

from app.core.market import STOCK_CODE_PATH_PATTERN, is_hk_code
from app.financial_data.hk.analysis_support import get_hk_market_overview, get_hk_stock_profile
from app.financial_data.hk.schemas import HKStockQuote, HKStockQuotePage
from app.modules.analysis.key_levels import resolve_key_levels
from app.modules.analysis.prompts import build_user_prompt
from app.modules.analysis.research import (
    ANALYSIS_RESEARCH_SPEC,
    HK_ANALYSIS_RESEARCH_SPEC,
    research_stock,
)


def test_is_hk_code_distinguishes_markets():
    assert is_hk_code("00700")
    assert is_hk_code("700")
    assert is_hk_code("hk00700")
    assert is_hk_code("HK700")
    # A 股 6 位、带交易所后缀、以及非法字符都不能被误判为港股
    assert not is_hk_code("600519")
    assert not is_hk_code("600519.SH")
    assert not is_hk_code("123456")
    assert not is_hk_code("abc")
    assert not is_hk_code("")


def test_hk_spec_only_exposes_hk_capable_tools():
    """港股 spec 绝不能引用 A 股口径工具：它们对港股会直接抛错。"""
    tool_names = set(HK_ANALYSIS_RESEARCH_SPEC.tool_names)
    assert "get_hk_stock_profile" in tool_names
    assert "get_hk_stock_kline" in tool_names
    assert "get_hk_stock_technical_indicators" in tool_names
    assert "get_hk_market_overview" in tool_names
    for a_share_only in (
        "get_stock_info",
        "get_stock_valuation_detail",
        "analyze_financials",
        "get_stock_news",
        "get_stock_sentiment",
        "get_stock_risk_data",
        "get_market_overview",
    ):
        assert a_share_only not in tool_names

    # profile / technical / market 是硬门槛，其余必须允许降级，否则港股必然因缺证据而失败
    fatal_keys = {
        requirement.key
        for requirement in HK_ANALYSIS_RESEARCH_SPEC.requirements
        if requirement.fatal
    }
    assert fatal_keys == {"profile", "technical", "market"}
    assert "valuation" not in fatal_keys
    assert "fundamental" not in fatal_keys


def test_hk_spec_requirements_only_reference_declared_tools():
    declared = set(HK_ANALYSIS_RESEARCH_SPEC.tool_names)
    for requirement in HK_ANALYSIS_RESEARCH_SPEC.requirements:
        assert set(requirement.tool_names) <= declared


def test_a_share_spec_unchanged():
    """A 股 spec 必须仍然使用原有工具集，不被港股分流污染。"""
    tool_names = set(ANALYSIS_RESEARCH_SPEC.tool_names)
    assert "get_stock_info" in tool_names
    assert "analyze_financials" in tool_names
    assert "get_hk_stock_profile" not in tool_names


@pytest.mark.asyncio
async def test_research_stock_dispatches_by_market():
    a_share = AsyncMock(return_value="a-share-result")
    hk = AsyncMock(return_value="hk-result")
    with patch(
        "app.modules.analysis.research.run_agentic_research",
        new=a_share,
    ):
        assert await research_stock("600519", "20260101") == "a-share-result"
    assert ANALYSIS_RESEARCH_SPEC in [call.args[0] for call in a_share.await_args_list]

    with patch(
        "app.modules.analysis.research.run_agentic_research",
        new=hk,
    ):
        assert await research_stock("00700", "20260101") == "hk-result"
    spec, task = hk.await_args_list[0].args[0], hk.await_args_list[0].args[1]
    assert spec is HK_ANALYSIS_RESEARCH_SPEC
    assert spec.name != ANALYSIS_RESEARCH_SPEC.name
    assert "港股" in task


@pytest.mark.asyncio
async def test_research_stock_dispatches_without_zero_padding():
    with patch(
        "app.modules.analysis.research.run_agentic_research",
        new=AsyncMock(return_value="ok"),
    ) as run:
        await research_stock("700", "20260101")
    assert run.await_args_list[0].args[0] is HK_ANALYSIS_RESEARCH_SPEC


def test_hk_tools_accept_hk_codes_and_reject_a_share_codes():
    """工具参数 schema 必须放行 1-5 位港股代码，否则 Agent 会在校验阶段就被打回。"""
    from app.agentic.catalog import registry
    from app.agentic.tools.registration import register_all_tools
    from app.agentic.tools.validation import ToolArgumentsError, coerce_arguments

    register_all_tools()
    profile_schema = registry._tools["get_hk_stock_profile"].parameters
    for accepted in ("00700", "700", "hk00700"):
        assert coerce_arguments({"code": accepted}, profile_schema) == {"code": accepted}
    # 6 位 A 股代码不能被港股工具接受，否则 Agent 会把 A 股当成港股分析
    with pytest.raises(ToolArgumentsError):
        coerce_arguments({"code": "600519"}, profile_schema)

    # A 股工具的反向约束仍然生效
    a_share_schema = registry._tools["get_stock_info"].parameters
    with pytest.raises(ToolArgumentsError):
        coerce_arguments({"code": "00700"}, a_share_schema)

    assert coerce_arguments({}, registry._tools["get_hk_market_overview"].parameters) == {}


def test_prompt_marks_hk_currency_and_gaps():
    hk_prompt = build_user_prompt({
        "stock_code": "00700",
        "analysis_date": "20260101",
        "market": "hk",
        "agent_summary": "s",
        "agent_evidence": "e",
        "agent_evidence_gaps": "港股财务与分部质量",
    })
    assert "交易市场：hk" in hk_prompt
    assert "港股财务与分部质量" in hk_prompt

    cn_prompt = build_user_prompt({
        "stock_code": "600519",
        "analysis_date": "20260101",
        "market": "cn",
        "agent_summary": "s",
        "agent_evidence": "e",
        "agent_evidence_gaps": "无",
    })
    assert "交易市场：cn" in cn_prompt


@pytest.mark.asyncio
async def test_key_levels_use_unadjusted_hk_kline():
    from app.domain.market import KlineData, KlineItem

    items = [
        KlineItem(
            date=f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}",
            open=100.0 + i,
            close=101.0 + i,
            high=102.0 + i,
            low=99.0 + i,
            volume=1000.0,
            amount=100000.0,
        )
        for i in range(60)
    ]
    kline = KlineData(code="00700", period="daily", adjust="none", items=items, source="sina")
    with patch(
        "app.modules.analysis.key_levels.get_kline",
        new=AsyncMock(return_value=kline),
    ) as mock_kline:
        levels = await resolve_key_levels("00700")
    assert mock_kline.await_args.kwargs["adjust"] == "none"
    assert levels.current_price == 160.0


@pytest.mark.asyncio
async def test_key_levels_keep_qfq_for_a_share():
    from app.domain.market import KlineData

    kline = KlineData(code="600519", period="daily", adjust="qfq", items=[], source="tdx")
    with patch(
        "app.modules.analysis.key_levels.get_kline",
        new=AsyncMock(return_value=kline),
    ) as mock_kline:
        await resolve_key_levels("600519")
    assert mock_kline.await_args.kwargs["adjust"] == "qfq"


@pytest.mark.asyncio
async def test_load_stock_info_routes_hk_to_hk_profile():
    """分析页的 stock_info 必须走港股快照；A 股的 get_basic_info 对港股会抛错。"""
    from app.financial_data.stock.profile.schemas import StockBasicInfo
    from app.modules.analysis.page_service import _load_stock_info

    hk_info = StockBasicInfo(code="00700", name="腾讯控股", current_price=400.0)
    with (
        patch(
            "app.modules.analysis.page_service._load_hk_stock_info",
            new=AsyncMock(return_value=hk_info),
        ) as mock_hk,
        patch(
            "app.modules.analysis.page_service.get_basic_info",
            new=AsyncMock(return_value=StockBasicInfo(code="600519", name="贵州茅台")),
        ) as mock_cn,
    ):
        assert await _load_stock_info("00700") is hk_info
        mock_hk.assert_awaited_once_with("00700")
        mock_cn.assert_not_awaited()

        await _load_stock_info("600519")
        mock_cn.assert_awaited_once_with("600519")
        mock_hk.assert_awaited_once_with("00700")


@pytest.mark.asyncio
async def test_load_hk_stock_info_only_maps_quote_facts():
    """港股基础资料只能映射行情能证明的字段，不得凭空填 A 股口径的行业与估值。"""
    from app.modules.analysis.page_service import _load_hk_stock_info

    with patch(
        "app.financial_data.hk.service.hk_market_service.get_stock_quotes",
        new=AsyncMock(return_value=HKStockQuotePage(
            items=[HKStockQuote(code="00700", name="腾讯控股", price=400.0)],
            total=1,
            page=1,
            page_size=50,
        )),
    ):
        info = await _load_hk_stock_info("700")

    assert (info.code, info.name, info.current_price) == ("00700", "腾讯控股", 400.0)
    assert info.exchange_industry is None
    assert info.pe_ttm is None
    assert info.pb is None
    assert info.market_cap is None
    assert info.concepts is None


@pytest.mark.asyncio
async def test_get_hk_stock_profile_returns_quote():
    page = HKStockQuotePage(
        items=[HKStockQuote(code="00700", name="腾讯控股", price=400.0, change_pct=1.2)],
        total=1,
        page=1,
        page_size=50,
        source="sina",
    )
    with patch(
        "app.financial_data.hk.service.hk_market_service.get_stock_quotes",
        new=AsyncMock(return_value=page),
    ):
        profile = await get_hk_stock_profile("700")
    assert profile["quote"]["code"] == "00700"
    assert profile["quote"]["name"] == "腾讯控股"
    assert profile["source"] == "sina"


@pytest.mark.asyncio
async def test_get_hk_stock_profile_raises_when_missing():
    page = HKStockQuotePage(items=[], total=0, page=1, page_size=50, source="sina")
    with patch(
        "app.financial_data.hk.service.hk_market_service.get_stock_quotes",
        new=AsyncMock(return_value=page),
    ):
        with pytest.raises(LookupError):
            await get_hk_stock_profile("00700")


@pytest.mark.asyncio
async def test_get_hk_market_overview_returns_indices():
    from app.domain.market import IndexItem, MarketIndices

    indices = MarketIndices(indices=[IndexItem(code="HSI", name="恒生指数", price=20000.0)])
    with patch(
        "app.financial_data.hk.service.hk_market_service.get_index_quotes",
        new=AsyncMock(return_value=indices),
    ):
        overview = await get_hk_market_overview()
    assert overview["indices"]["indices"][0]["code"] == "HSI"


def _page_loaders(valuation: AsyncMock):
    """显式注入 loaders：DEFAULT_ANALYSIS_PAGE_LOADERS 在导入时就绑定了函数对象，
    patch 模块属性对它无效，那样写出来的断言会是空断言。"""
    from app.domain.market import KlineData
    from app.financial_data.stock.profile.schemas import StockBasicInfo
    from app.modules.analysis.page_service import AnalysisPageLoaders

    kline = KlineData(code="00700", period="daily", adjust="none", items=[], source="sina")
    return AnalysisPageLoaders(
        stock_info=AsyncMock(return_value=StockBasicInfo(code="00700", name="腾讯控股")),
        kline=AsyncMock(return_value=kline),
        intraday=AsyncMock(return_value=None),
        valuation=valuation,
        cached_analysis=AsyncMock(return_value=None),
    )


@pytest.mark.asyncio
async def test_analysis_page_skips_valuation_for_hk():
    """港股没有 A 股口径估值：必须直接标记不可用，而不是建好协程再等它超时。"""
    from app.modules.analysis.page_service import get_analysis_page_data

    valuation = AsyncMock(return_value=None)
    page = await get_analysis_page_data(
        "00700",
        user_id=1,
        cache_ttl=0,
        section_timeout_seconds=5.0,
        loaders=_page_loaders(valuation),
    )

    valuation.assert_not_awaited()
    assert page.valuation is None
    assert page.unavailable_sections == ["valuation"]
    assert page.partial is True
    # 其余分区仍应正常返回，不因跳过估值而整体降级
    assert page.kline is not None


@pytest.mark.asyncio
async def test_analysis_page_keeps_valuation_for_a_share():
    from app.modules.analysis.page_service import get_analysis_page_data

    valuation = AsyncMock(return_value=None)
    page = await get_analysis_page_data(
        "600519",
        user_id=1,
        cache_ttl=0,
        section_timeout_seconds=5.0,
        loaders=_page_loaders(valuation),
    )

    valuation.assert_awaited_once_with("600519")
    assert "valuation" not in page.unavailable_sections


def test_delete_analysis_accepts_hk_code(tmp_path):
    """港股 1-5 位代码此前被 6 位长度校验挡住，分析记录无法删除。"""
    from app.modules.analysis.persistence import repository

    stock_dir = tmp_path / "00700"
    stock_dir.mkdir()
    record = stock_dir / "20260101.json"
    record.write_text("{}", encoding="utf-8")

    with (
        patch.object(repository, "_user_stock_dir", return_value=stock_dir),
        patch.object(repository, "_version_path") as mock_version,
        patch.object(repository.cache, "delete_many"),
        patch.object(repository.history_store, "delete_history_row"),
    ):
        mock_version.return_value = tmp_path / "versions" / "20260101" / ("0" * 32 + ".json")
        assert repository.delete_analysis("00700", "20260101", 1) is True

    assert not record.exists()


@pytest.mark.parametrize(
    "code",
    ["00700", "700", "hk00700", "600519", "000001", "300750", "688981", "920001", "430047"],
)
def test_stock_code_path_pattern_accepts_both_markets(code):
    """路径约束必须同时放行 6 位 A 股与 1-5 位港股；此前只放行 6 位会让港股 422。"""
    assert re.fullmatch(STOCK_CODE_PATH_PATTERN, code, re.IGNORECASE)


@pytest.mark.parametrize("code", ["123456", "abc", "", "60051a", "00700x"])
def test_stock_code_path_pattern_rejects_invalid(code):
    assert not re.fullmatch(STOCK_CODE_PATH_PATTERN, code, re.IGNORECASE)


def test_analysis_job_route_accepts_hk_code():
    """端到端确认提交路由不再对港股返回 422。"""
    from app.api.routes import workflows

    route = next(
        item
        for item in workflows.router.routes
        if getattr(item, "path", None) == "/analysis/{code}" and "POST" in getattr(item, "methods", set())
    )
    code_field = next(
        parameter for parameter in route.dependant.path_params if parameter.name == "code"
    )
    pattern = code_field.field_info.metadata[0].pattern
    assert pattern == STOCK_CODE_PATH_PATTERN
    assert re.fullmatch(pattern, "00700")
    assert re.fullmatch(pattern, "600519")


def test_bot_analyze_command_accepts_hk_code():
    """Bot 的 /analyze 曾硬编码 6 位数字，港股代码同样会被挡下。"""
    from app.modules.bot.commands.analyze import AnalyzeCommand

    command = AnalyzeCommand()
    for accepted in ("00700", "700", "hk00700", "600519"):
        assert command.validate_args([accepted]) is None
    for rejected in ("123456", "abc", ""):
        assert command.validate_args([rejected]) is not None
    assert command.validate_args([]) is not None


def test_delete_analysis_rejects_invalid_code(tmp_path):
    from app.modules.analysis.persistence import repository

    stock_dir = tmp_path / "stock"
    stock_dir.mkdir()
    record = stock_dir / "20260101.json"
    record.write_text("{}", encoding="utf-8")

    with patch.object(repository, "_user_stock_dir", return_value=stock_dir) as mock_dir:
        # 非数字代码、非法日期、7 位代码都必须在触碰文件前就被拒绝
        assert repository.delete_analysis("abcdef", "20260101", 1) is False
        assert repository.delete_analysis("00700", "2026010", 1) is False
        assert repository.delete_analysis("1234567", "20260101", 1) is False
        mock_dir.assert_not_called()

    assert record.exists()