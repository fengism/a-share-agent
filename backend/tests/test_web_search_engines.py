import time

import pytest
from lxml import html

from app.infrastructure.providers.web_search import (
    BaiduSearchNoApi,
    So360SearchNoApi,
    _age_in_days,
    _is_360_internal,
    _is_baidu_internal,
    _join_text,
)

BAIDU_ITEM = """
<div class="result c-container" tpl="www_index" mu="https://finance.example.com/a/1.html">
  <h3 class="cosc-title"><a href="http://www.baidu.com/link?url=OPAQUE_TOKEN"
     >贵州茅台<em>发布</em>2025年报</a></h3>
  <div data-module="abstract"><div><span>营收 1688.38 亿元，<em>同比</em>下降 1.21%</span></div></div>
</div>
"""

BAIDU_INTERNAL_ITEM = """
<div class="result c-container" tpl="wenda_generate" mu="http://nourl.ubs.baidu.com/61344">
  <h3><a href="http://www.baidu.com/link?url=X">AI 摘要卡</a></h3>
</div>
"""

BAIDU_REDIRECT_ITEM = """
<div class="result c-container" tpl="www_index">
  <h3><a href="http://www.baidu.com/link?url=KEEPME">没有 mu 属性的条目</a></h3>
</div>
"""

SO360_WEB_ITEM = """
<li class="res-list"><h3 class="res-title">
  <a href="https://www.so.com/link?m=OPAQUE" data-mdurl="https://news.example.com/b/1.html"
     >储能<em>产业链</em>拆解</a></h3>
  <p class="res-desc"><span class="gray g-c-gray">2026-09-20 - </span>正文摘要</p>
</li>
"""

SO360_NEWS_ITEM = """
<li class="res-list full-txtnews" data-url="https://stock.example.com/c/1.shtml">
  <a href="https://stock.example.com/c/1.shtml" title="宁德时代回应储能话题">
    <h3 class="g-title"><div class="g-txt-inner"><em>宁德时代</em>回应储能话题</div></h3>
    <p class="g-ellipsis3 summary">证券之星消息，<em>宁德时代</em>9月24日答复投资者问题。</p>
    <span class="g-linkinfo-txt g-c-gray time">2天前</span>
  </a>
</li>
"""

SO360_OLD_NEWS_ITEM = """
<li class="res-list full-txtnews" data-url="https://stock.example.com/c/old.shtml">
  <a href="https://stock.example.com/c/old.shtml" title="三个月前的旧闻">
    <h3 class="g-title"><div class="g-txt-inner">三个月前的旧闻</div></h3>
    <span class="g-linkinfo-txt g-c-gray time">MONTHS_AGO</span>
  </a>
</li>
"""

SO360_INTERNAL_ITEM = """
<li class="res-list"><h3 class="res-title">
  <a href="https://www.so.com/link?m=X" data-mdurl="https://tv.360kan.com/s?q=储能">影视垂直聚合</a></h3>
</li>
"""


def _tree(fragment: str):
    # 三个月前的绝对时间戳，落在 half_year 内、week 外。
    stamp = time.strftime("%Y-%m-%d", time.localtime(time.time() - 90 * 86400))
    return html.fromstring(f"<div>{fragment.replace('MONTHS_AGO', stamp)}</div>")


class TestJoinText:
    def test_glues_across_tag_boundaries(self):
        # 百度用 <em> 包裹命中词，节点边界切在词中间；加分隔符会把中文切碎。
        assert _join_text(["贵州茅台", "发", "2025", "年报:"]) == "贵州茅台发2025年报:"

    def test_collapses_source_indentation(self):
        assert _join_text(["截至 ", "2025年", "\n            , 净利"]) == "截至 2025年 , 净利"

    def test_keeps_genuine_spaces(self):
        assert _join_text(["英伟达", "NVIDIA H100"]) == "英伟达NVIDIA H100"

    def test_drops_empty_nodes(self):
        assert _join_text(["", "  ", "正文"]) == "正文"


class TestBaiduInternal:
    def test_flags_baidu_hosts(self):
        for url in (
            "http://nourl.ubs.baidu.com/61344",
            "https://baike.baidu.com/item/x",
            "https://zhidao.baidu.com/question/1",
            "https://www.baidu.com/baidu.php?url=abc",
        ):
            assert _is_baidu_internal(url), url

    def test_keeps_followable_redirect(self):
        assert not _is_baidu_internal("http://www.baidu.com/link?url=abc")

    def test_keeps_external_hosts(self):
        for url in ("https://finance.example.com/a", "https://xueqiu.com/1", "https://notbaidu.com/a"):
            assert not _is_baidu_internal(url), url


class Test360Internal:
    def test_flags_360_hosts(self):
        for url in (
            "https://www.so.com/link?m=x",
            "https://tv.360kuai.com/s?q=x",
            "https://ai.so.com/search/abc",
            "https://www.360doc.com/x",
        ):
            assert _is_360_internal(url), url

    def test_keeps_external_hosts(self):
        for url in ("https://news.example.com/a", "https://chuneng.ofweek.com/tag-x"):
            assert not _is_360_internal(url), url


class TestAgeInDays:
    def test_relative_units(self):
        now = time.time()
        assert _age_in_days("刚刚前", now) is None
        assert _age_in_days("5分钟前", now) == pytest.approx(5 / 1440)
        assert _age_in_days("3小时前", now) == pytest.approx(3 / 24)
        assert _age_in_days("2天前", now) == pytest.approx(2)
        assert _age_in_days("1周前", now) == pytest.approx(7)
        # 360 两种写法都出现过：1个月前 / 1月前。
        assert _age_in_days("1个月前", now) == pytest.approx(30)
        assert _age_in_days("1月前", now) == pytest.approx(30)

    def test_absolute_date_uses_day_granularity(self):
        # 绝对时间只取到「日」，从当天零点起算：今天的条目算 0.x 天，昨天的算 1.x 天。
        today = time.strftime("%Y-%m-%d", time.localtime())
        assert 0 <= _age_in_days(today, time.time()) < 1
        yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
        assert 1 <= _age_in_days(yesterday, time.time()) < 2
        three_days_ago = time.strftime("%Y-%m-%d", time.localtime(time.time() - 3 * 86400))
        assert 3 <= _age_in_days(three_days_ago, time.time()) < 4

    def test_unparseable_returns_none(self):
        assert _age_in_days("更新时间未知", time.time()) is None
        assert _age_in_days("", time.time()) is None

    def test_future_date_clamps_to_zero(self):
        stamp = time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400))
        assert _age_in_days(stamp, time.time()) == 0.0


class TestBaiduParse:
    def test_prefers_mu_over_redirect_href(self):
        # 前端展示的是这个 href；用 mu 才是一手地址和可展示的链接。
        results = BaiduSearchNoApi().parse_results(_tree(BAIDU_ITEM))
        assert len(results) == 1
        assert results[0]["href"] == "https://finance.example.com/a/1.html"
        assert results[0]["title"] == "贵州茅台发布2025年报"
        assert "1688.38" in results[0]["body"]

    def test_drops_baidu_internal_cards(self):
        assert BaiduSearchNoApi().parse_results(_tree(BAIDU_INTERNAL_ITEM)) == []

    def test_keeps_redirect_when_mu_missing(self):
        results = BaiduSearchNoApi().parse_results(_tree(BAIDU_REDIRECT_ITEM))
        assert [item["href"] for item in results] == ["http://www.baidu.com/link?url=KEEPME"]


class TestSo360Parse:
    def test_web_mode_uses_data_mdurl(self):
        engine = So360SearchNoApi()
        engine._time_range = "any"
        results = engine.parse_results(_tree(SO360_WEB_ITEM))
        assert [item["href"] for item in results] == ["https://news.example.com/b/1.html"]
        assert results[0]["title"] == "储能产业链拆解"

    def test_drops_360_internal(self):
        engine = So360SearchNoApi()
        engine._time_range = "any"
        assert engine.parse_results(_tree(SO360_INTERNAL_ITEM)) == []

    def test_news_mode_reads_data_url_and_title_attr(self):
        engine = So360SearchNoApi()
        engine._time_range = "week"
        results = engine.parse_results(_tree(SO360_NEWS_ITEM))
        assert [item["href"] for item in results] == ["https://stock.example.com/c/1.shtml"]
        # a 包裹 h3（与通用站 h3 > a 相反），标题取 a/@title 才是干净的原文。
        assert results[0]["title"] == "宁德时代回应储能话题"
        assert "证券之星消息" in results[0]["body"]

    def test_time_window_excludes_stale_items(self):
        engine = So360SearchNoApi()
        engine._time_range = "week"
        assert engine.parse_results(_tree(SO360_OLD_NEWS_ITEM)) == []
        engine._time_range = "half_year"
        assert len(engine.parse_results(_tree(SO360_OLD_NEWS_ITEM))) == 1
    def test_time_window_drops_items_without_timestamp(self):
        # 解析不出时间就丢弃，而不是当作满足时间范围。
        no_stamp = """
        <li class="res-list full-txtnews" data-url="https://stock.example.com/c/x.shtml">
          <a href="https://stock.example.com/c/x.shtml" title="无时间标注"><h3>无时间标注</h3></a>
        </li>
        """
        engine = So360SearchNoApi()
        engine._time_range = "day"
        assert engine.parse_results(_tree(no_stamp)) == []
        engine._time_range = "any"
        assert len(engine.parse_results(_tree(no_stamp))) == 1

    def test_default_time_range_is_any(self):
        # parse_results 可能被单独调用，不能因为 search() 没跑过就崩。
        assert So360SearchNoApi().parse_results(_tree(SO360_OLD_NEWS_ITEM))


class TestBaiduSearchUrl:
    def test_pins_classic_layout_and_page_size(self):
        url = BaiduSearchNoApi().build_search_url("贵州茅台 业绩", max_results=10)
        # tn 锁定服务端版式：移动端 UA 默认返回纯 JS 卡片，解析不到任何链接。
        assert "tn=baiduhome_pg" in url
        assert "ie=utf-8" in url
        assert "rn=20" in url

    def test_page_size_scales_with_request(self):
        engine = BaiduSearchNoApi()
        # 取 2 倍原始结果，过滤掉站内卡片和重复稿后才够切到调用方要的条数。
        assert "rn=20" in engine.build_search_url("q", max_results=10)
        assert "rn=20" in engine.build_search_url("q", max_results=99)
        # 未指定时按默认 10 条推算，并夹在 10~20 之间。
        assert "rn=20" in engine.build_search_url("q")
        assert "rn=10" in engine.build_search_url("q", max_results=1)

    def test_time_range_adds_gpc_filter(self):
        engine = BaiduSearchNoApi()
        assert "gpc=" in engine.build_search_url("q", time_range="week")
        assert "gpc=" not in engine.build_search_url("q", time_range="any")

    def test_query_is_percent_encoded(self):
        assert "%E8%B4%B5%E5%B7%9E" in BaiduSearchNoApi().build_search_url("贵州茅台")


class TestSo360SearchUrl:
    def test_time_constrained_uses_news_endpoint(self):
        engine = So360SearchNoApi()
        assert "news.so.com" in engine.build_search_url("q", time_range="week")
        assert "rank=pdate" in engine.build_search_url("q", time_range="week")
        assert "www.so.com/s" in engine.build_search_url("q", time_range="any")
