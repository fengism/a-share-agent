"""验证分析报告 PDF 生成去除执行工具等技术噪音，并支持港股/A股市扬与货币规范。"""

from types import SimpleNamespace
from app.modules.analysis.pdf_service import generate_research_report_html
from app.modules.analysis.provenance import AnalysisProvenance, EvidenceFreshness


def test_generate_research_report_html_cleans_execution_tools():
    # 模拟包含港股和A股工具的分析结果
    provenance = AnalysisProvenance(
        research_started_at="2026-10-06T10:00:00",
        research_completed_at="2026-10-06T10:05:00",
        report_regenerated=False,
        freshness_note="重新生成仅跳过分析报告缓存",
        evidence=[
            EvidenceFreshness(
                tool_name="get_hk_stock_profile",
                evidence_id="call_1",
                sources=["官方披露"],
                data_dates=["2026-10-05"],
                report_periods=["2026H1"],
                cache_status="live",
            ),
            EvidenceFreshness(
                tool_name="get_hk_stock_kline",
                evidence_id="call_2",
                sources=["行情接口"],
                data_dates=["2026-10-06"],
                report_periods=[],
                cache_status="cached",
            ),
            EvidenceFreshness(
                tool_name="web_search",
                evidence_id="call_3",
                sources=["https://news.example.com/1"],
                data_dates=["2026-10-06"],
                report_periods=[],
                cache_status="live",
            ),
            EvidenceFreshness(
                tool_name="web_search",
                evidence_id="call_4",
                sources=["https://news.example.com/2"],
                data_dates=["2026-10-06"],
                report_periods=[],
                cache_status="live",
            ),
        ],
    )

    result = SimpleNamespace(
        stock_code="00700",
        stock_name="腾讯控股",
        analysis_date="2026-10-06",
        report_id="rep_1234567890abcdef1234567890abcdef",
        generated_at="2026-10-06 10:05:00",
        signal="buy",
        confidence=0.88,
        current_price=380.0,
        estimated_price_range=(350.0, 450.0),
        overall_summary="腾讯控股基本面稳健，游戏与企服业务持续复苏。",
        overall_rating=9,
        provenance=provenance,
        research_framework=None,
        risk_warnings=["海外宏观波动"],
        scenarios=None,
    )

    html = generate_research_report_html(result)

    # 1. 验证不含原始"证据工具"列头与原始内部工具函数标识
    assert "<th>证据工具</th>" not in html
    assert "get_hk_stock_profile</td>" not in html
    assert "get_hk_stock_kline</td>" not in html

    # 2. 验证转换为规范的投研数据维度名称
    assert "港股基本面画像与行业属性" in html
    assert "港股历史行情与K线走势" in html
    assert "公开市场资讯与权威研报" in html
    assert "数据考察维度" in html

    # 3. 验证 web_search 被聚合为单一维度（而不是重复出现多个 web_search 维度行）
    assert html.count("公开市场资讯与权威研报") == 1

    # 4. 验证时效说明与附录放置
    assert "附录 · 数据时效与信息来源审计" in html
    assert "rep_1234567890" in html

    # 5. 验证港股特有规范（港币符号与港股上市公司标识）
    assert "HK$380.00" in html
    assert "HK$350.00 - HK$450.00" in html
    assert "港股上市公司" in html
    assert "A股上市公司" not in html
    assert "港股智能投研体系" in html


def test_generate_research_report_html_a_share_defaults():
    result = SimpleNamespace(
        stock_code="600519",
        stock_name="贵州茅台",
        analysis_date="2026-10-06",
        report_id="rep_ashare123456",
        generated_at="2026-10-06 10:00:00",
        signal="buy",
        confidence=0.9,
        current_price=1700.0,
        estimated_price_range=(1600.0, 1900.0),
        overall_summary="白酒龙头稳健增长。",
        overall_rating=9,
        provenance=None,
        research_framework=None,
        risk_warnings=[],
        scenarios=None,
    )

    html = generate_research_report_html(result)
    assert "¥1700.00" in html
    assert "A股上市公司" in html
    assert "A股智能投研体系" in html
