"""证据完整性的回归护栏。

四类「证据看起来比实际充分」的问题：

1. fatal 取证门被空结果满足。``_has_public_sources`` 曾只要求「正文 60 字」，而
   ``web_search`` 零结果时的 ``detail_hint``（约 60 字）加 query 回显就够了——
   ``count: 0`` 恰恰说明什么都没取到。
2. ``agent_evidence_id`` 把 content 全文计入摘要，``web_fetch`` 每次都带新的
   ``fetched_at``，于是同一篇材料在主调研与补证阶段各读一次就得到两个 id：
   去重永久失效，重读被计成「新增证据」。
3. 工具自报 ``ok: false`` 但没给原因时，``serialize_result`` 会把它包成 ``ok: true``。
4. fatal 门没过时抛的异常把本轮已采集的证据全部丢掉，pipeline 只能退化成一句
   硬编码文案 + 公共数据继续合成。
"""
import json

from app.agentic.contracts import (
    AgentEvidence,
    AgentEvidenceInsufficientError,
    agent_evidence_id,
)
from app.agentic.tools.serialization import serialize_result
from app.modules.industry_chain.evidence import compact_industry_evidence
from app.modules.industry_chain.research import (
    _has_market_context,
    _has_public_sources,
)

_SEARCH_HINT = (
    "搜索结果仅包含标题和摘要；需要详细内容时，使用 web_fetch 抓取对应 URL，"
    "需要同时阅读多个结果时使用 fetch_urls。"
)


def _evidence(tool_name: str, payload: dict, arguments: str = '{"query":"x"}') -> AgentEvidence:
    return AgentEvidence(
        tool_call_id="c1",
        tool_name=tool_name,
        arguments=arguments,
        content=serialize_result(payload),
        is_error=False,
    )


def _zero_result_search() -> AgentEvidence:
    return _evidence(
        "web_search",
        {
            "query": "储能 行业 规模 竞争 上游 下游",
            "engine": "baidu",
            "time_range": "half_year",
            "language": "zh",
            "count": 0,
            "results": [],
            "detail_hint": _SEARCH_HINT,
        },
    )


def _real_search() -> AgentEvidence:
    return _evidence(
        "web_search",
        {
            "query": "储能 行业 规模 竞争 上游 下游",
            "engine": "baidu",
            "count": 2,
            "results": [
                {
                    "title": "储能产业上游材料与中游电池环节竞争格局",
                    "url": "https://news.example.com/a.html",
                    "snippet": "上半年储能行业规模同比增长，上游锂价回落，中游产能利用率抬升。",
                    "engine": "baidu",
                },
                {
                    "title": "储能需求与下游应用展望",
                    "url": "https://stock.example.com/b.html",
                    "snippet": "下游需求持续释放，行业空间打开。",
                    "engine": "baidu",
                },
            ],
            "detail_hint": _SEARCH_HINT,
        },
    )


def _real_body() -> AgentEvidence:
    return _evidence(
        "web_fetch",
        {
            "url": "https://news.example.com/a.html",
            "title": "储能产业研究",
            "content": "储能行业规模在 2026 年继续扩张，上游材料价格回落，中游电池环节竞争加剧，"
            "下游需求由大储与工商储共同驱动。",
            "content_type": "html",
            "fetched_at": "2026-09-26T10:00:00+00:00",
        },
        arguments='{"url":"https://news.example.com/a.html"}',
    )


def _structured_quote() -> AgentEvidence:
    return _evidence(
        "get_stock_info",
        {
            "code": "600519",
            "name": "贵州茅台",
            "industry": "白酒",
            "market_cap": 18000,
            "listing_date": "2001-08-27",
        },
        arguments='{"code":"600519"}',
    )


class TestFatalGatesRejectEmptyResults:
    def test_zero_result_search_does_not_count_as_public_source(self):
        evidence = _zero_result_search()
        # 先确认这确实是「什么都没取到」的载荷。
        assert json.loads(evidence.content)["data"]["count"] == 0
        assert _has_public_sources(evidence) is False

    def test_zero_result_search_does_not_count_as_market_context(self):
        assert _has_market_context(_zero_result_search()) is False

    def test_real_search_results_still_satisfy_both(self):
        evidence = _real_search()
        assert _has_public_sources(evidence) is True
        assert _has_market_context(evidence) is True

    def test_real_body_satisfies_both(self):
        evidence = _real_body()
        assert _has_public_sources(evidence) is True
        assert _has_market_context(evidence) is True

    def test_structured_evidence_with_dimension_words_still_counts(self):
        # 结构化数据没有链接，但「上游/中游/下游 + 规模」确实是取回的内容，
        # 不能因为收紧成内容单元判定就被整体误杀。
        evidence = _evidence(
            "get_industry_list",
            {
                "industry": "储能",
                "chain": "上游锂材料、中游电池电芯、下游系统集成",
                "market_size": "2026 年国内储能市场规模约 6000 亿元",
                "competitors": ["宁德时代", "亿纬锂能"],
            },
            arguments='{"name":"储能"}',
        )
        assert _has_market_context(evidence) is True

    def test_quote_without_dimension_words_does_not_claim_market_boundary(self):
        # 单只股票的基本信息不含产业链维度，不该被当成「市场与产业边界」已取证。
        assert _has_market_context(_structured_quote()) is False

    def test_echo_fields_alone_never_satisfy_the_gates(self):
        # 只把 query 换成长文本、依然 0 结果：门槛不能被回显字段撑起来。
        payload = {
            "query": "行业市场规模竞争上游中游下游需求出货芯片算力空间增速渗透应用客户" * 3,
            "engine": "baidu",
            "count": 0,
            "results": [],
            "detail_hint": _SEARCH_HINT,
        }
        evidence = _evidence("web_search", payload)
        assert _has_public_sources(evidence) is False
        assert _has_market_context(evidence) is False


class TestEvidenceIdIgnoresVolatileFields:
    @staticmethod
    def _fetched_at(ts: str) -> AgentEvidence:
        return AgentEvidence(
            tool_call_id="c1",
            tool_name="web_fetch",
            arguments='{"url":"https://news.example.com/a.html"}',
            content=serialize_result(
                {
                    "url": "https://news.example.com/a.html",
                    "title": "储能产业研究",
                    "content": "储能行业规模继续扩张。" * 20,
                    "fetched_at": ts,
                }
            ),
            is_error=False,
        )

    def test_same_document_read_twice_has_one_id(self):
        first = self._fetched_at("2026-09-26T10:00:00+00:00")
        second = self._fetched_at("2026-09-26T10:05:00+00:00")
        assert agent_evidence_id(first) == agent_evidence_id(second)

    def test_genuinely_different_content_keeps_distinct_ids(self):
        other = AgentEvidence(
            tool_call_id="c2",
            tool_name="web_fetch",
            arguments='{"url":"https://news.example.com/a.html"}',
            content=serialize_result(
                {
                    "url": "https://news.example.com/a.html",
                    "title": "完全不同的另一篇",
                    "content": "另一篇文章讲的是白酒行业。",
                }
            ),
            is_error=False,
        )
        assert agent_evidence_id(self._fetched_at("2026-09-26T10:00:00+00:00")) != agent_evidence_id(other)

    def test_nested_volatile_fields_are_stripped(self):
        base = {
            "url": "https://x.example.com/a",
            "sections": [
                {"heading": "一", "text": "正文一" * 20, "fetched_at": "2026-09-26T10:00:00+00:00"},
            ],
        }
        other = json.loads(json.dumps(base))
        other["sections"][0]["fetched_at"] = "2026-09-26T11:00:00+00:00"
        first = AgentEvidence(tool_call_id="c1", tool_name="read_pdf", arguments="{}",
                               content=serialize_result(base), is_error=False)
        second = AgentEvidence(tool_call_id="c2", tool_name="read_pdf", arguments="{}",
                                content=serialize_result(other), is_error=False)
        assert agent_evidence_id(first) == agent_evidence_id(second)

    def test_non_json_content_still_hashes(self):
        evidence = AgentEvidence(
            tool_call_id="c1", tool_name="web_fetch", arguments="{}", content="纯文本正文", is_error=False
        )
        assert agent_evidence_id(evidence).startswith("ev_")


class TestToolReportedFailureIsNotUpgraded:
    def test_ok_false_without_message_stays_an_error(self):
        payload = json.loads(serialize_result({"ok": False, "output": "", "error": ""}))
        assert payload["ok"] is False
        assert payload["error"]["code"] == "tool_reported_error"
        assert "未提供原因" in payload["error"]["message"]

    def test_tool_reported_code_is_preserved(self):
        payload = json.loads(
            serialize_result({"ok": False, "output": "", "error_code": "sandbox_unavailable", "error": ""})
        )
        assert payload["error"]["code"] == "sandbox_unavailable"

    def test_original_payload_is_kept_as_data(self):
        payload = json.loads(serialize_result({"ok": False, "output": "", "error": ""}))
        assert payload["data"]["output"] == ""
        assert "ok" not in payload["data"]

    def test_normal_success_is_untouched(self):
        payload = json.loads(serialize_result({"ok": True, "value": 1}))
        assert payload == {"ok": True, "data": {"ok": True, "value": 1}}

    def test_inner_ok_false_is_not_masked(self):
        # 修复前这里会输出 {"ok": true, "data": {"ok": false, ...}}。
        raw = serialize_result({"ok": False, "error": ""})
        assert json.loads(raw)["ok"] is not True


class TestInsufficientEvidenceIsNotDiscarded:
    def test_error_carries_summary_and_evidence(self):
        evidence = (_real_body(), _real_search())
        error = AgentEvidenceInsufficientError(
            "Agent 调研证据不足：相关公司",
            summary="已读完两篇材料",
            evidence=evidence,
        )
        assert error.summary == "已读完两篇材料"
        assert error.evidence == evidence

    def test_defaults_keep_it_backward_compatible(self):
        error = AgentEvidenceInsufficientError("缺证据")
        assert error.summary == ""
        assert error.evidence == ()

    def test_carried_evidence_is_usable_for_synthesis(self):
        evidence = (_real_body(),)
        error = AgentEvidenceInsufficientError("缺证据", summary="s", evidence=evidence)
        _, rendered, stats = compact_industry_evidence(error.evidence)
        assert rendered  # 真的能渲染出来，而不是退化成一句硬编码文案
        assert stats is not None
