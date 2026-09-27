"""Bot /analyze 命令回复内容的守卫测试。"""

import pytest

from app.modules.analysis.models import (
    AnalysisResult,
    FactorAnalysis,
    InvestorActionPlan,
    ValuationFramework,
    ValuationScenario,
    ValuationScenarios,
)
from app.modules.bot.commands.analyze import AnalyzeCommand, _format_analysis_result
from app.modules.bot.models import BotResponse


def _make_result(**overrides) -> AnalysisResult:
    fields = dict(
        stock_code="600519",
        stock_name="贵州茅台",
        analysis_date="2026-09-27",
        current_price=1500.0,
        fundamental=FactorAnalysis(score=8, summary="基本面稳健"),
        technical=FactorAnalysis(score=7, summary="趋势向上"),
        sentiment=FactorAnalysis(score=6, summary="情绪中性"),
        overall_rating=8,
        overall_summary="综合看多，核心业务具备定价权与护城河。",
        estimated_price_range=(1450.0, 1650.0),
        signal="buy",
        confidence=0.85,
        key_factors=["高端白酒龙头", "直销占比提升"],
        risk_warnings=["消费复苏不及预期", "政策限制高端消费"],
    )
    fields.update(overrides)
    return AnalysisResult(**fields)


def _make_framework() -> object:
    from app.modules.analysis.models import InvestmentResearchFramework

    return InvestmentResearchFramework(
        actions=InvestorActionPlan(
            new_investor_action="buy",
            buy_or_add_range=(1420.0, 1480.0),
            thesis_breakers=["高端酒批价持续跌破 2000 元"],
        ),
        valuation=ValuationFramework(
            margin_of_safety="20%",
            scenarios=ValuationScenarios(
                bear=ValuationScenario(scenario="bear", fair_value_range=(1100.0, 1250.0)),
                base=ValuationScenario(scenario="base", fair_value_range=(1450.0, 1650.0)),
                bull=ValuationScenario(scenario="bull", fair_value_range=(1800.0, 2000.0)),
            ),
        ),
    )


def test_format_contains_core_sections():
    text = _format_analysis_result(_make_result())
    assert "贵州茅台" in text and "综合评分 8/10" in text
    assert "核心结论" in text
    assert "综合目标区间：1450.00 - 1650.00" in text
    assert "关键因子" in text and "高端白酒龙头" in text
    assert "风险提示" in text and "消费复苏不及预期" in text
    # 无研究框架时，框架相关段落不出现也不报错
    assert "悲观情景区间" not in text


def test_format_includes_framework_details():
    text = _format_analysis_result(_make_result(research_framework=_make_framework()))
    assert "建议买入/加仓区间：1420.00 - 1480.00" in text
    assert "悲观情景区间：1100.00 - 1250.00" in text
    assert "基准情景区间：1450.00 - 1650.00" in text
    assert "乐观情景区间：1800.00 - 2000.00" in text
    assert "安全边际：20%" in text
    assert "新资金建议：买入" in text
    assert "观点失效条件" in text and "批价持续跌破 2000 元" in text


async def test_execute_reports_progress_before_result(monkeypatch):
    progress: list[BotResponse] = []

    class _Context:
        service_user_id = 1

        async def report_progress(self, response: BotResponse) -> None:
            progress.append(response)

    async def fake_run_analysis(code: str, user_id: int) -> AnalysisResult:
        assert code == "600519" and user_id == 1
        return _make_result()

    monkeypatch.setattr("app.modules.bot.commands.analyze.run_analysis", fake_run_analysis)

    response = await AnalyzeCommand().execute(None, ["600519"], _Context())

    assert len(progress) == 1
    assert "已开始分析 600519" in progress[0].text
    assert response.title == "股票分析 · 贵州茅台"
    assert "估值与操作" in response.text


@pytest.mark.parametrize("args,expected", [
    ([], "请输入股票代码"),
    (["60051"], "6 位数字"),
    (["60051a"], "6 位数字"),
])
def test_validate_args_rejects_bad_input(args, expected):
    message = AnalyzeCommand().validate_args(args)
    assert message is not None and expected in message


def test_validate_args_accepts_six_digits():
    assert AnalyzeCommand().validate_args(["600519"]) is None
