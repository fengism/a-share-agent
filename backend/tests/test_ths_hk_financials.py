"""同花顺港股 F10 财务 JSON 解析与统一字段映射测试。"""

from __future__ import annotations

import json

import pytest
from bs4 import BeautifulSoup

from app.infrastructure.providers.ths.hk_financials import (
    fetch_hk_financial_metrics,
    fetch_hk_financial_statement,
    parse_hk_finance_block,
)


def _block(titles, report, year=None) -> dict:
    return {"title": ["时间\\科目", *titles], "report": report, "year": year or report}


def _page(**blocks) -> str:
    return (
        "<html><body>"
        + "".join(f'<p id="{name}">{json.dumps(payload, ensure_ascii=False)}</p>' for name, payload in blocks.items())
        + "</body></html>"
    )


class _FakeResponse:
    def __init__(self, html: str) -> None:
        self.content = html.encode("utf-8")
        self.encoding: str | None = None

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding or "utf-8")


class _FakeTransport:
    def __init__(self, html: str) -> None:
        self.html = html
        self.urls: list[str] = []

    def request(self, method, url, **kwargs):  # noqa: ANN001
        self.urls.append(url)
        return _FakeResponse(self.html)


def test_parse_statement_keeps_raw_fields_and_adds_standard_fields() -> None:
    debt = _block(
        [
            ["报表年结日", "", "L"],
            ["原始货币", "", "L"],
            ["报表核心指标", "", "TN"],
            ["*资产合计", "元", "L"],
            ["*负债合计", "元", "L"],
            ["流动资产", "元", "T"],
            ["存货", "元", "L"],
        ],
        [
            ["2025-06-30", "2024-12-31"],
            ["12-31", "12-31"],
            ["港元", "港元"],
            ["ignored", "ignored"],
            ["1,200", "1,000"],
            ["300", "250"],
            ["800", "700"],
            ["--", "20"],
        ],
    )
    rows = parse_hk_finance_block(BeautifulSoup(_page(debt=debt), "html.parser"), "debt", limit=1)

    assert len(rows) == 1
    row = rows[0]
    assert row["REPORT_DATE"] == "2025-06-30"
    assert row["CURRENCY"] == "港元"
    assert row["资产合计"] == 1200.0
    assert row["TOTAL_ASSETS"] == 1200.0
    assert row["TOTAL_LIABILITIES"] == 300.0
    assert row["TOTAL_CURRENT_ASSETS"] == 800.0
    assert row["存货"] is None
    assert "报表核心指标" not in row
    assert "*资产合计" not in row
    assert row["__units__"]["资产合计"] == "元"


def test_parse_year_period_and_text_negative_percent_values() -> None:
    keyindex = _block(
        [
            ["报表年结日", "", "L"],
            ["审计意见", "", "L"],
            ["净资产收益率", "%", "L"],
            ["每股收益-基本", "元", "L"],
        ],
        [
            ["2025-06-30"],
            ["12-31"],
            ["未经审计"],
            ["-2.50%"],
            ["0.125"],
        ],
        [
            ["2024", "2023"],
            ["03-31", "12-31"],
            ["审计", "审计"],
            ["10.5", "--"],
            ["1.2", "1.0"],
        ],
    )
    rows = parse_hk_finance_block(
        BeautifulSoup(_page(keyindex=keyindex), "html.parser"),
        "keyindex",
        period_type="year",
    )
    assert [row["REPORT_DATE"] for row in rows] == ["2024-03-31", "2023-12-31"]
    assert rows[0]["审计意见"] == "审计"
    assert rows[0]["净资产收益率"] == 10.5
    assert rows[1]["净资产收益率"] is None


def test_fetch_statement_maps_url_and_profit_cashflow_fields() -> None:
    benefit = _block(
        [["营业收入", "元", "T"], ["归属于母公司股东利润", "元", "L"]],
        [["2025-06-30"], ["100"], ["20"]],
    )
    transport = _FakeTransport(_page(benefit=benefit))
    rows = fetch_hk_financial_statement(transport, "00700", "profit")
    assert transport.urls == ["https://basic.10jqka.com.cn/new/HK0700/finance.html"]
    assert rows[0]["OPERATE_INCOME"] == 100.0
    assert rows[0]["PARENT_NETPROFIT"] == 20.0

    cash = _block(
        [["经营活动现金流量净额", "元", "T"], ["投资活动现金流量净额", "元", "T"]],
        [["2025-06-30"], ["30"], ["-10"]],
    )
    rows = fetch_hk_financial_statement(_FakeTransport(_page(cash=cash)), "hk00700", "cashflow")
    assert rows[0]["NETCASH_OPERATE"] == 30.0
    assert rows[0]["NETCASH_INVEST"] == -10.0


def test_fetch_metrics_localizes_names_and_scales_percentages() -> None:
    keyindex = _block(
        [
            ["营业收入", "元", "L"],
            ["归母净利润", "元", "L"],
            ["净资产收益率", "%", "L"],
            ["资产负债率", "%", "L"],
            ["每股收益-基本", "元", "L"],
        ],
        [["2025-06-30"], ["1,000"], ["200"], ["10.56"], ["26.12"], ["5.52"]],
    )
    result = fetch_hk_financial_metrics(_FakeTransport(_page(keyindex=keyindex)), "09999")
    assert result["code"] == "09999"
    assert result["latest_report_date"] == "2025-06-30"
    assert result["metrics"]["营收"] == 1000.0
    assert result["metrics"]["净利润"] == 200.0
    assert result["metrics"]["净资产收益率"] == pytest.approx(0.1056)
    assert result["metrics"]["资产负债率"] == pytest.approx(0.2612)
    assert result["metrics"]["基本每股收益"] == 5.52


@pytest.mark.parametrize(
    ("html", "block_id", "message"),
    [
        ("<html></html>", "debt", "缺少数据块"),
        ('<p id="debt">not-json</p>', "debt", "格式异常"),
        ('<p id="debt">{}</p>', "debt", "结构异常"),
    ],
)
def test_parse_rejects_missing_or_malformed_blocks(html, block_id, message) -> None:
    with pytest.raises(ValueError, match=message):
        parse_hk_finance_block(BeautifulSoup(html, "html.parser"), block_id)


def test_rejects_invalid_period_limit_and_a_share() -> None:
    soup = BeautifulSoup(_page(debt=_block([], [["2025-06-30"]])), "html.parser")
    with pytest.raises(ValueError, match="周期类型"):
        parse_hk_finance_block(soup, "debt", period_type="quarter")
    with pytest.raises(ValueError, match="记录数"):
        parse_hk_finance_block(soup, "debt", limit=0)
    with pytest.raises(ValueError, match="仅支持港股"):
        fetch_hk_financial_statement(_FakeTransport(""), "600519", "balance")
