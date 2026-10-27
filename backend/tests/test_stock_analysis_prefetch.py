from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agentic.contracts import AgentEvidence, AgentResearchSpec, AgentRoundResult, EvidenceRequirement
from app.agentic.protocol import ToolResultInfo
from app.agentic.research import run_agentic_research
from app.modules.analysis.prefetch import _build_prefetch_plan, prefetch_stock_baseline
from app.modules.analysis.research import ANALYSIS_RESEARCH_SPEC


def test_prefetch_plan_separation():
    cn_plan = _build_prefetch_plan("600519")
    cn_tools = [tool for tool, _ in cn_plan]
    assert "get_stock_info" in cn_tools
    assert "get_stock_valuation_detail" in cn_tools
    assert "analyze_financials" in cn_tools
    assert "get_stock_technical_indicators" in cn_tools
    assert "get_hk_stock_profile" not in cn_tools

    hk_plan = _build_prefetch_plan("00700")
    hk_tools = [tool for tool, _ in hk_plan]
    assert "get_hk_stock_profile" in hk_tools
    assert "get_hk_stock_industry_comparison" in hk_tools
    assert "get_stock_info" not in hk_tools


def test_analysis_research_spec_tools():
    tools = set(ANALYSIS_RESEARCH_SPEC.tool_names)
    assert "get_interactive_qa" in tools
    assert "get_restricted_shares_lift" in tools
    assert "get_stock_documents" in tools
    assert "analyze_financials" in tools


@pytest.mark.asyncio
async def test_prefetch_stock_baseline_success():
    events = []

    async def _event_cb(ev):
        events.append(ev)

    mock_tool = AsyncMock()
    mock_tool.name = "get_stock_info"

    mock_result = ToolResultInfo(
        tool_call_id="call-1",
        name="get_stock_info",
        content='{"code":"600519","name":"贵州茅台","pe_ttm":25.5}',
        is_error=False,
    )

    with patch("app.modules.analysis.prefetch.registry.get_tool", return_value=mock_tool), \
         patch("app.modules.analysis.prefetch.registry.execute_tool", AsyncMock(return_value=mock_result)):
        evidences = await prefetch_stock_baseline("600519", event_callback=_event_cb)

    assert len(evidences) == len(_build_prefetch_plan("600519"))
    assert all(isinstance(item, AgentEvidence) for item in evidences)
    assert any(e.type == "tool_call" for e in events)
    assert any(e.type == "tool_result" for e in events)


@pytest.mark.asyncio
async def test_prefetch_stock_baseline_partial_failure():
    async def _mock_execute(call, execution_context=None):
        if "analyze_financials" in call.function.name:
            raise TimeoutError("upstream timeout")
        return ToolResultInfo(
            tool_call_id=call.id,
            name=call.function.name,
            content='{"ok": true, "data": 123}',
            is_error=False,
        )

    with patch("app.modules.analysis.prefetch.registry.get_tool", return_value=AsyncMock()), \
         patch("app.modules.analysis.prefetch.registry.execute_tool", side_effect=_mock_execute):
        evidences = await prefetch_stock_baseline("600519")

    # analyze_financials 失败，其他成功
    total_planned = len(_build_prefetch_plan("600519"))
    assert len(evidences) == total_planned - 1
    assert not any(item.tool_name == "analyze_financials" for item in evidences)


@pytest.mark.asyncio
async def test_run_agentic_research_with_initial_evidence():
    spec = AgentResearchSpec(
        name="test-spec",
        display_name="测试规范",
        system_prompt="sys",
        tool_names=("tool_a", "tool_b"),
        requirements=(
            EvidenceRequirement(key="req_a", label="维度A", tool_names=("tool_a",)),
            EvidenceRequirement(key="req_b", label="维度B", tool_names=("tool_b",)),
        ),
        max_rounds=2,
    )

    initial_evidence = [
        AgentEvidence(
            tool_call_id="call-init-a",
            tool_name="tool_a",
            arguments='{"code":"000001"}',
            content='{"ok": true, "metric": 999}',
        )
    ]

    round_calls = []

    class _MockSession:
        async def run(self, message, allowed_tool_names, event_callback=None, tool_call_reserve=0):
            round_calls.append({"message": message, "tools": allowed_tool_names})
            # 模拟在首轮直接返回维度 B 的证据并结束
            return AgentRoundResult(
                summary="调研完成，结论全面。",
                evidence=(
                    AgentEvidence(
                        tool_call_id="call-b",
                        tool_name="tool_b",
                        arguments='{"code":"000001"}',
                        content='{"ok": true, "data": 888}',
                    ),
                ),
            )

    class _MockRuntime:
        def open_session(self, s, settings=None):
            from contextlib import asynccontextmanager
            @asynccontextmanager
            async def _ctx():
                yield _MockSession()
            return _ctx()

    result = await run_agentic_research(
        spec,
        "请调研股票 000001",
        runtime=_MockRuntime(),
        initial_evidence=initial_evidence,
    )

    # 验证只有 1 轮（因为初始已有 A，首轮补齐 B，直接完成）
    assert len(round_calls) == 1
    # 验证第一轮消息中已告知系统已预取维度 A
    assert "系统已自动预取并纳入证据库的维度" in round_calls[0]["message"]
    assert "维度A" in round_calls[0]["message"]
    # 验证结果中包含初始证据和首轮证据两者
    tool_names_in_result = {e.tool_name for e in result.evidence}
    assert "tool_a" in tool_names_in_result
    assert "tool_b" in tool_names_in_result
    assert not result.evidence_gaps
