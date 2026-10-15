"""宏观资讯聚合：统计局/央行列表解析、时间窗口过滤与利率提取。"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.financial_data.market.macro import feed as feed_module
from app.infrastructure.providers.nbs import _parse_nbs_releases, _parse_pbc_list


def test_parse_nbs_releases_dedupes_responsive_links() -> None:
    html = """
    <ul>
      <li>
        <a class="fl pc_1600" href="./202610/t20261014_1.html" target="_blank" title='2026年9月份居民消费价格同比上涨0.9%'>CPI</a>
        <a class="fl mhide pc1200" href="./202610/t20261014_1.html" target="_blank" title='2026年9月份居民消费价格同比上涨0.9%'>CPI</a>
        <a class="fl pchide" href="./202610/t20261014_1.html" target="_blank" title='2026年9月份居民消费价格同比上涨0.9%'>CPI</a>
        <span>2026-10-14</span>
      </li>
      <li>
        <a href="./202609/t20260930_2.html" title='2026年9月中国采购经理指数运行情况'>PMI</a>
        <span>2026-09-30</span>
      </li>
      <li><a href="/nav/">导航项（无日期）</a></li>
    </ul>
    """
    items = _parse_nbs_releases(html)
    assert len(items) == 2  # 响应式重复链接按 URL 去重；无日期项被排除
    assert items[0]["published_at"] == "2026-10-14"
    assert items[0]["url"] == "https://www.stats.gov.cn/sj/zxfb/202610/t20261014_1.html"
    assert items[0]["source"] == "国家统计局"
    assert items[1]["title"] == "2026年9月中国采购经理指数运行情况"


def test_parse_pbc_list_excludes_sidebar_without_date() -> None:
    html = """
    <a href="/hanglingdao/1/index.html" onclick="void(0)" title="领导活动" istitle="true">领导活动</a>
    <table><tbody><tr><td class="unline">
      <a href="/rmyh/3963412/3963426/2026091019504481025/index.html" onclick="void(0)" title="政策解读A" istitle="true">政策解读A</a> 2026-09-10
    </td></tr></tbody></table>
    """
    items = _parse_pbc_list(html, base_url="https://www.pbc.gov.cn", source="中国人民银行")
    assert len(items) == 1
    assert items[0]["title"] == "政策解读A"
    assert items[0]["published_at"] == "2026-09-10"
    assert items[0]["url"] == "https://www.pbc.gov.cn/rmyh/3963412/3963426/2026091019504481025/index.html"


def _row(item_id: str, title: str, published_at: str, source: str) -> dict:
    return {"id": item_id, "title": title, "url": f"https://example.com/{item_id}", "published_at": published_at, "source": source}


@pytest.fixture(autouse=True)
def _clear_cache():
    feed_module.cache.clear()
    yield
    feed_module.cache.clear()


async def test_get_macro_feed_filters_window_and_extracts_rates(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date.today()
    recent = today.isoformat()
    old = (today - timedelta(days=400)).isoformat()
    policy_recent = (today - timedelta(days=200)).isoformat()

    async def fake_fetch(method_name: str) -> list[dict]:
        if method_name == "fetch_latest_releases":
            return [_row("r1", "CPI", recent, "国家统计局"), _row("r2", "OLD", old, "国家统计局")]
        if method_name == "fetch_pbc_news":
            return [_row("n1", "央行新闻", recent, "中国人民银行")]
        return [_row("p1", "政策解读", policy_recent, "中国人民银行")]

    async def fake_metric(operation: str) -> list[dict]:
        if operation == "lpr":
            return [
                {"TIME": "2026-09-20", "LPR1Y": 3.0, "LPR5Y": 3.5},
                {"TIME": "2026-08-20", "LPR1Y": 3.1, "LPR5Y": 3.6},
            ]
        return [
            {"REPORT_PERIOD": "ON", "REPORT_DATE": "2026-10-15", "IR_RATE": 1.3, "CHANGE_RATE": -0.5, "LATEST_RECORD": 1},
        ]

    monkeypatch.setattr(feed_module, "_fetch_list", fake_fetch)
    monkeypatch.setattr(feed_module, "_load_macro_metric", fake_metric)

    result = await feed_module.get_macro_feed(days=31)

    assert [item.title for item in result.releases] == ["CPI"]  # 超窗口条目被过滤
    assert [item.title for item in result.policy_news] == ["央行新闻"]
    assert [item.title for item in result.policy_readings] == ["政策解读"]  # 政策解读用 365 天窗口
    assert result.status == "available"
    assert result.failed_sources == []

    lpr = next(rate for rate in result.rates if rate.key == "lpr1y")
    assert lpr.value == 3.0
    assert lpr.change_bp == pytest.approx(-10.0)  # (3.0 - 3.1) * 100
    shibor = next(rate for rate in result.rates if rate.key == "shibor_on")
    assert shibor.value == 1.3
    assert shibor.change_bp == pytest.approx(-0.5)


async def test_get_macro_feed_marks_partial_when_a_source_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(method_name: str) -> list[dict]:
        if method_name == "fetch_pbc_news":
            raise RuntimeError("pbc down")
        return [_row("r1", "CPI", date.today().isoformat(), "国家统计局")]

    async def fake_metric(operation: str) -> list[dict]:
        raise RuntimeError("rates down")

    monkeypatch.setattr(feed_module, "_fetch_list", fake_fetch)
    monkeypatch.setattr(feed_module, "_load_macro_metric", fake_metric)

    result = await feed_module.get_macro_feed(days=31)

    assert result.status == "partial"
    assert "央行新闻发布" in result.failed_sources
    assert [item.title for item in result.releases] == ["CPI"]


async def test_get_macro_feed_caches_within_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_fetch(method_name: str) -> list[dict]:
        calls.append(method_name)
        return [_row("r1", "CPI", date.today().isoformat(), "国家统计局")]

    async def fake_metric(operation: str) -> list[dict]:
        return []

    monkeypatch.setattr(feed_module, "_fetch_list", fake_fetch)
    monkeypatch.setattr(feed_module, "_load_macro_metric", fake_metric)

    await feed_module.get_macro_feed(days=31)
    first_count = len(calls)
    await feed_module.get_macro_feed(days=31)

    assert len(calls) == first_count  # 第二次命中缓存，不再请求数据源
