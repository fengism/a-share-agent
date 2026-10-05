"""同花顺港股主营构成抓取：报告期选择、维度解析、子项与合计行剔除。"""

from __future__ import annotations

import pytest

from app.infrastructure.providers.ths.hk_composition import (
    fetch_hk_revenue_breakdown,
    parse_hk_revenue_composition,
)

_TABLE_TEMPLATE = """
<table class="m_table m_hl company{extra}">
  <tr><td rowspan="{n}">按业务分</td><td colspan="3">项目名称</td><td>营业收入 (人民币元)</td><td>占比 (%)</td></tr>
  {business_rows}
  <tr><td colspan="4">营业额</td><td></td><td>100</td></tr>
  {region_rows}
</table>
"""


def _table(*, extra: str = "", business_rows: str = "", region_rows: str = "", n: int = 3) -> str:
    return _TABLE_TEMPLATE.format(
        extra=extra, business_rows=business_rows, region_rows=region_rows, n=n
    )


def _row(name: str, share: str, *, span: str = 'colspan="3"') -> str:
    return f'<tr><td {span}>{name}</td><td></td><td>{share}</td></tr>'


def _page(*tables: str) -> str:
    return f"<html><body>{''.join(tables)}</body></html>"


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.encoding: str | None = None

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding or "utf-8", errors="replace")

    def raise_for_status(self) -> None:
        return None


class _FakeTransport:
    def __init__(self, html: str) -> None:
        self._html = html
        self.urls: list[str] = []

    def request(self, method, url, *, headers=None, timeout=None, **kwargs):  # noqa: ANN001
        self.urls.append(url)
        return _FakeResponse(self._html.encode("utf-8"))


def _parse(html: str) -> dict:
    from bs4 import BeautifulSoup

    from app.infrastructure.providers.ths.hk_composition import _current_period_table

    table = _current_period_table(BeautifulSoup(html, "html.parser"))
    assert table is not None
    return parse_hk_revenue_composition(table)


def test_parses_business_dimension_and_drops_total_row() -> None:
    html = _page(_table(
        business_rows=_row("增值服务", "48.06") + _row("网络广告", "21.27"),
    ))
    result = _parse(html)
    assert result["by_business"] == [
        {"class_name": "增值服务", "is_sub_item": False, "revenue_share_pct": 48.06},
        {"class_name": "网络广告", "is_sub_item": False, "revenue_share_pct": 21.27},
    ]
    # 「营业额」是合计行，不能混进构成项
    assert all(item["class_name"] != "营业额" for item in result["by_business"])


def test_marks_parenthesised_rows_as_sub_items_and_strips_parens() -> None:
    html = _page(_table(business_rows=(
        _row("利息净收入", "72.94")
        + _row("(公司银行业务)", "33.97")
        + _row("（个人银行业务）", "34.16")
    )))
    items = _parse(html)["by_business"]
    assert [item["is_sub_item"] for item in items] == [False, True, True]
    # 括号只是版式标记，不属于构成项名称
    assert [item["class_name"] for item in items] == ["利息净收入", "公司银行业务", "个人银行业务"]


def test_parses_region_dimension_into_separate_list() -> None:
    html = _page(_table(
        business_rows=_row("增值服务", "48.06"),
        region_rows=(
            '<tr><td rowspan="2">按地区分</td><td colspan="3">中国</td><td></td><td>88.08</td></tr>'
            + _row("其他", "11.92", span='colspan="4"')
            + _row("合计", "100", span='colspan="4"')
        ),
    ))
    result = _parse(html)
    assert [item["class_name"] for item in result["by_region"]] == ["中国", "其他"]
    assert all(item["class_name"] != "合计" for item in result["by_region"])


def test_negative_and_tiny_shares_are_preserved() -> None:
    """同花顺会出现负占比与四位小数，不能因取值小就丢弃。"""
    html = _page(_table(business_rows=(
        _row("投资性证券净收益", "4.73") + _row("(个人银行业务)", "-0.03") + _row("(其他业务)", "0.0005")
    )))
    shares = [item["revenue_share_pct"] for item in _parse(html)["by_business"]]
    assert shares == [4.73, -0.03, 0.0005]


def test_picks_current_period_table_over_hidden_history() -> None:
    """当期表的 class 不含 none，历史期含 none；不能把三期混在一起。"""
    from bs4 import BeautifulSoup

    from app.infrastructure.providers.ths.hk_composition import _current_period_table

    current = _table(business_rows=_row("当前期项目", "10"))
    history = [
        _table(extra=' none', business_rows=_row(f"历史期项目{i}", str(i + 1)))
        for i in range(2)
    ]
    soup = BeautifulSoup(_page(current, *history), "html.parser")
    chosen = _current_period_table(soup)
    assert chosen is not None
    items = parse_hk_revenue_composition(chosen)["by_business"]
    assert [item["class_name"] for item in items] == ["当前期项目"]


def test_returns_empty_dimensions_when_no_composition_table() -> None:
    html = "<html><body><ul class='main_intro_list'><li>主营业务：某公司</li></ul></body></html>"
    transport = _FakeTransport(html)
    result = fetch_hk_revenue_breakdown(transport, "00700")
    assert result["by_business"] == []
    assert result["by_region"] == []
    assert result["source"] == "ths"


def test_fetch_builds_four_digit_hk_url_and_disclaims_currency() -> None:
    html = _page(_table(business_rows=_row("增值服务", "48.06")))
    transport = _FakeTransport(html)
    result = fetch_hk_revenue_breakdown(transport, "00700")
    assert transport.urls == ["https://basic.10jqka.com.cn/new/HK0700/operate.html"]
    assert result["symbol"] == "HK0700"
    assert result["code"] == "00700"
    # 金额单位随公司报表币种而定且金额本身缺失，不得声称人民币
    assert result["amount_unit"] is None
    assert result["amount_unit_inferred"] is False
    # 金额一律留空，不按占比反推
    assert all("revenue" not in item for item in result["by_business"])


def test_fetch_decodes_hk_page_as_utf8() -> None:
    html = _page(_table(business_rows=_row("金融科技及企业服务", "29.44")))
    transport = _FakeTransport(html)
    result = fetch_hk_revenue_breakdown(transport, "00700")
    assert result["by_business"][0]["class_name"] == "金融科技及企业服务"


def test_fetch_rejects_a_share_code() -> None:
    transport = _FakeTransport(_page(_table()))
    with pytest.raises(ValueError, match="仅支持港股"):
        fetch_hk_revenue_breakdown(transport, "600519")
