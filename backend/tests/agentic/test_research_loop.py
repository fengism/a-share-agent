"""外层调研循环（research.py）的特征测试。

这是内层工具循环之上的第二层：外层按**证据需求清单**决定是否再跑一轮，内层按
「模型不再要工具」结束。此前这个文件 22% 覆盖、主循环 150 行零覆盖，任何重构都是盲改；
这里先只依赖公开契约（AgentResearchSpec / AgentRoundResult / AgenticResearchResult /
AgentEvent）把行为钉住。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from app.agentic.contracts import (
    AgentEvidence,
    AgentEvidenceInsufficientError,
    AgentResearchSpec,
    AgentRoundResult,
    EvidenceRequirement,
)
from app.agentic.research import run_agentic_research

_DOC = "web_fetch"
_FIN = "get_stock_financial"
_SEARCH = "web_search"


def _evidence(tool_name: str, content: str = '{"ok":true,"data":{"v":1}}') -> AgentEvidence:
    return AgentEvidence(
        tool_call_id=f"call-{tool_name}", tool_name=tool_name, arguments="{}", content=content,
    )


def _spec(**overrides) -> AgentResearchSpec:
    defaults: dict[str, Any] = {
        "name": "probe",
        "display_name": "探针调研",
        "system_prompt": "sys",
        "tool_names": (_SEARCH, _DOC, _FIN),
        "requirements": (
            EvidenceRequirement(key="doc", label="公告正文", tool_names=(_DOC,)),
            EvidenceRequirement(key="fin", label="财务数据", tool_names=(_FIN,)),
        ),
        "max_rounds": 3,
    }
    defaults.update(overrides)
    return AgentResearchSpec(**defaults)


class _Session:
    def __init__(self, results: list[AgentRoundResult], calls: list[dict]) -> None:
        self._results = list(results)
        self._calls = calls

    async def run(self, message, allowed_tool_names, event_callback=None, tool_call_reserve=0):
        self._calls.append({
            "message": message,
            "tools": tuple(allowed_tool_names),
            "reserve": tool_call_reserve,
        })
        if not self._results:
            raise AssertionError("会话被调用了超出预期的轮数")
        return self._results.pop(0)


class _Runtime:
    def __init__(self, session: _Session) -> None:
        self._session = session

    @asynccontextmanager
    async def open_session(self, spec, settings=None):
        yield self._session


async def _run(spec, results, *, events=None, evidence_seen=None, **kwargs):
    calls: list[dict] = []
    runtime = _Runtime(_Session(results, calls))

    async def on_event(event):
        if events is not None:
            events.append(event)

    def on_evidence(item):
        if evidence_seen is not None:
            evidence_seen.append(item)

    outcome = await run_agentic_research(
        spec, "分析这家公司", runtime,
        event_callback=on_event if events is not None else None,
        evidence_callback=on_evidence if evidence_seen is not None else None,
        **kwargs,
    )
    return outcome, calls


def _full_round() -> AgentRoundResult:
    return AgentRoundResult(
        summary="已取得公告与财务",
        evidence=(_evidence(_DOC), _evidence(_FIN)),
        tool_calls_remaining=10,
    )


# --- 轮次决策 --------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_round_satisfying_every_requirement_stops_immediately():
    result, calls = await _run(_spec(), [_full_round()])

    assert len(calls) == 1
    assert result.evidence_gaps == ()
    assert "公告与财务" in result.summary


@pytest.mark.asyncio
async def test_missing_requirement_triggers_a_gap_round_with_only_that_tool():
    first = AgentRoundResult(
        summary="只有公告", evidence=(_evidence(_DOC),), tool_calls_remaining=10,
    )
    result, calls = await _run(_spec(), [first, _full_round()])

    assert len(calls) == 2
    assert calls[1]["tools"] == (_FIN,), "缺口轮只该下发缺失维度对应的工具"
    assert "财务数据" in calls[1]["message"]
    assert "必须实际调用工具" in calls[1]["message"]
    assert result.evidence_gaps == ()


@pytest.mark.asyncio
async def test_no_progress_breaks_the_loop_even_with_rounds_left():
    """新增数据条数不等于缺口缩小；不缩小就停，避免无关材料驱动空转。"""
    stuck = AgentRoundResult(
        summary="只有公告", evidence=(_evidence(_DOC),), tool_calls_remaining=10,
    )
    calls: list[dict] = []
    runtime = _Runtime(_Session([stuck] * 4, calls))
    with pytest.raises(AgentEvidenceInsufficientError):
        await run_agentic_research(_spec(max_rounds=4), "问题", runtime)

    # 首轮 + 一次无进展的缺口轮后必须停止，不能把 4 轮额度耗光。
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_round_limit_is_respected():
    stuck = AgentRoundResult(summary="只有公告", evidence=(_evidence(_DOC),), tool_calls_remaining=10)
    calls: list[dict] = []
    runtime = _Runtime(_Session([stuck] * 5, calls))

    with pytest.raises(AgentEvidenceInsufficientError):
        await run_agentic_research(_spec(max_rounds=2), "问题", runtime)

    assert len(calls) <= 2


@pytest.mark.asyncio
async def test_exhausted_tool_budget_stops_the_loop():
    broke = AgentRoundResult(
        summary="只有公告", evidence=(_evidence(_DOC),), tool_calls_remaining=0,
    )
    calls: list[dict] = []
    runtime = _Runtime(_Session([broke] * 3, calls))

    with pytest.raises(AgentEvidenceInsufficientError):
        await run_agentic_research(_spec(max_rounds=3), "问题", runtime)

    assert len(calls) == 1, "工具额度为 0 时不该再发起空轮次"


@pytest.mark.asyncio
async def test_followup_reserve_is_released_after_the_first_round():
    first = AgentRoundResult(summary="只有公告", evidence=(_evidence(_DOC),), tool_calls_remaining=10)
    _, calls = await _run(_spec(), [first, _full_round()])

    assert calls[0]["reserve"] == 8, "首轮为后续补查预留 8 次"
    assert calls[1]["reserve"] == 0, "补查轮不再锁定预留，否则每轮都扣同一批额度"


# --- 失败语义 --------------------------------------------------------------


@pytest.mark.asyncio
async def test_fatal_termination_propagates_instead_of_becoming_a_gap():
    fatal = AgentRoundResult(
        summary="", evidence=(), termination_reason="authentication_error", tool_calls_remaining=10,
    )
    from app.domain.llm import LLMInvalidResponseError

    with pytest.raises(LLMInvalidResponseError):
        await _run(_spec(), [fatal])


@pytest.mark.asyncio
async def test_stop_reason_clears_the_summary_and_marks_stopped_early():
    partial = AgentRoundResult(
        summary="半截结论", evidence=(_evidence(_DOC), _evidence(_FIN)),
        stop_reason="工具额度不足，提前收尾", tool_calls_remaining=0,
    )
    result, _ = await _run(_spec(), [partial])

    assert result.summary == "", "失败轮次的正文不能当作结论"
    assert result.stopped_early is True
    assert any("工具额度不足" in gap for gap in result.evidence_gaps)


@pytest.mark.asyncio
async def test_missing_fatal_requirement_carries_evidence_out():
    """证据不足抛错时必须带上已采集的证据，否则本轮读到的正文全部作废。"""
    only_doc = AgentRoundResult(summary="只有公告", evidence=(_evidence(_DOC),), tool_calls_remaining=0)

    with pytest.raises(AgentEvidenceInsufficientError) as excinfo:
        await _run(_spec(), [only_doc])

    error = excinfo.value
    assert "财务数据" in str(error)
    assert any(item.tool_name == _DOC for item in error.evidence)


@pytest.mark.asyncio
async def test_non_fatal_gap_degrades_instead_of_raising():
    spec = _spec(requirements=(
        EvidenceRequirement(key="doc", label="公告正文", tool_names=(_DOC,)),
        EvidenceRequirement(key="fin", label="财务数据", tool_names=(_FIN,), fatal=False),
    ))
    only_doc = AgentRoundResult(summary="只有公告", evidence=(_evidence(_DOC),), tool_calls_remaining=0)

    result, _ = await _run(spec, [only_doc])

    assert "财务数据" in result.evidence_gaps
    assert result.summary


# --- 事件与回调 ------------------------------------------------------------


@pytest.mark.asyncio
async def test_events_form_a_complete_trace():
    events: list = []
    await _run(_spec(), [_full_round()], events=events)

    types = [event.type for event in events]
    assert types[0] == "plan", f"事件流必须以计划开头，实际：{types[:3]}"
    assert "round_started" in types
    assert "round_completed" in types
    assert types[-1] == "done"


@pytest.mark.asyncio
async def test_each_evidence_item_is_reported_once():
    seen: list = []
    repeated = AgentRoundResult(
        summary="公告", evidence=(_evidence(_DOC), _evidence(_DOC)), tool_calls_remaining=10,
    )
    # 只要求公告正文：这样一轮就满足，不需要第二次会话调用。
    spec = _spec(requirements=(EvidenceRequirement(key="doc", label="公告正文", tool_names=(_DOC,)),))
    await _run(spec, [repeated], evidence_seen=seen)

    ids = [item.evidence_id for item in seen]
    assert len(ids) == len(set(ids)), "同一条证据不能被重复上报"


@pytest.mark.asyncio
async def test_document_guidance_replaces_the_default_retry_hint():
    first = AgentRoundResult(summary="只有公告", evidence=(_evidence(_DOC),), tool_calls_remaining=10)
    spec = _spec(document_search_guidance="先复用已取得的目录清单")

    _, calls = await _run(spec, [first, _full_round()])

    assert "先复用已取得的目录清单" in calls[1]["message"]
    assert "不得原样重复失败或低质量的查询" not in calls[1]["message"]


# --- 调研 system prompt ----------------------------------------------------


def test_research_system_prompt_keeps_the_clock_section_last():
    """prompt 前缀缓存不变量：时钟必须最后，否则它之后每一段都不可缓存。"""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.agentic.research import build_research_system_prompt

    prompt = build_research_system_prompt(
        _spec(), current_time=datetime(2026, 3, 1, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    sections = prompt.split("\n\n")
    assert sections[0].startswith("sys")
    assert sections[-1].startswith("## 运行时日期与时间")
    assert "2026-03-01 09:30:00" in sections[-1]


def test_research_system_prompt_only_adds_search_rules_when_search_is_available():
    from app.agentic.research import build_research_system_prompt

    with_search = build_research_system_prompt(_spec())
    without_search = build_research_system_prompt(_spec(tool_names=(_DOC, _FIN), requirements=()))

    assert "## 网页检索式规则" in with_search
    assert "half_year" in with_search
    assert "## 网页检索式规则" not in without_search
    # 数据源权威性规则任何情况下都在。
    assert "## 数据源权威性与冲突处理" in without_search


def test_document_guidance_replaces_the_default_search_rule_block():
    from app.agentic.research import build_research_system_prompt

    prompt = build_research_system_prompt(_spec(document_search_guidance="先复用已取得的目录"))
    assert "先复用已取得的目录" in prompt
    assert "## 网页检索式规则" not in prompt
