from app.agentic.tools.packs.web.search import (
    _encode_url,
    _is_tracking_param,
    _normalize_results,
    _title_identity,
    _url_identity,
)


class TestEncodeUrl:
    def test_encodes_bare_chinese_path(self):
        assert (
            _encode_url("https://news.qq.com/rain/a/中文标题")
            == "https://news.qq.com/rain/a/%E4%B8%AD%E6%96%87%E6%A0%87%E9%A2%98"
        )

    def test_encodes_space_even_though_it_is_ascii(self):
        # 空格是 ASCII，但 URL 里非法；曾经用 isascii() 做快速判断，导致这种 URL 漏出去。
        assert _encode_url("https://x.com/a b") == "https://x.com/a%20b"

    def test_encodes_control_characters(self):
        assert _encode_url("https://x.com/a\nb") == "https://x.com/a%0Ab"

    def test_is_idempotent_and_keeps_existing_escapes(self):
        once = _encode_url("https://x.com/a b?k=v%20w")
        assert _encode_url(once) == once
        assert "%20" in once

    def test_ascii_url_untouched(self):
        url = "https://xueqiu.com/9079826787/404579986?_ugc_source=ugcbaiducard"
        assert _encode_url(url) == url


class TestTrackingParam:
    def test_known_tracking_params_detected(self):
        for key in ("path", "app", "redirect_pc", "spm", "from", "wfr", "utm_source", "sid"):
            assert _is_tracking_param(key), key

    def test_content_identity_params_kept(self):
        # 这些承载内容身份，误剔会把两篇不同文章合并成一条。
        for key in ("id", "page", "docid", "docId", "q"):
            assert not _is_tracking_param(key), key


class TestUrlIdentity:
    def test_tracking_variants_merge(self):
        # 腾讯新闻对同一篇文章会同时给出带跟踪参数和不带跟踪参数两种地址。
        assert _url_identity("https://news.qq.com/rain/a/20260920A05HGF00?path=a&app=news&redirect_pc=1") == _url_identity(
            "https://news.qq.com/rain/a/20260920A05HGF00"
        )

    def test_scheme_www_fragment_and_trailing_slash_ignored(self):
        variants = [
            "https://www.163.com/dy/article/X1.html",
            "http://WWW.163.com/dy/article/X1.html/",
            "https://www.163.com/dy/article/X1.html#top",
        ]
        assert len({_url_identity(url) for url in variants}) == 1

    def test_different_ids_stay_distinct(self):
        assert _url_identity("https://x.com/a?id=1") != _url_identity("https://x.com/a?id=2")

    def test_different_pages_stay_distinct(self):
        assert _url_identity("https://x.com/a?page=2") != _url_identity("https://x.com/a?page=3")

    def test_query_order_does_not_matter(self):
        assert _url_identity("https://x.com/a?b=2&a=1") == _url_identity("https://x.com/a?a=1&b=2")


class TestTitleIdentity:
    def test_punctuation_and_case_ignored(self):
        assert _title_identity("LPR连续16个月持平,央行还在等什么?_腾讯新闻") == _title_identity(
            "LPR连续16个月持平 央行还在等什么 腾讯新闻"
        )

    def test_different_titles_stay_distinct(self):
        assert _title_identity("央行开展350亿元逆回购") != _title_identity("央行开展5000亿元买断式逆回购")


def _row(title, href, body="", engine="baidu"):
    return {"title": title, "href": href, "body": body, "engine": engine}


class TestNormalizeResults:
    def test_drops_non_http_schemes(self):
        rows = [_row("A", "ftp://x.com/a"), _row("B", "javascript:void(0)"), _row("C", "https://x.com/c")]
        out = _normalize_results(rows, "baidu", 10)
        assert [item["url"] for item in out] == ["https://x.com/c"]

    def test_drops_missing_title_or_netloc(self):
        rows = [_row("", "https://x.com/a"), _row("B", "https:///nohost"), _row("C", "https://x.com/c")]
        out = _normalize_results(rows, "baidu", 10)
        assert [item["title"] for item in out] == ["C"]

    def test_excludes_baijiahao_only_for_baidu_engine(self):
        rows = [_row("百家号", "https://baijiahao.baidu.com/s?id=1", engine="baidu")]
        assert _normalize_results(rows, "baidu", 10) == []
        # 非百度引擎不做这个排除，360 降级时不该把百家号一起丢掉。
        assert len(_normalize_results(rows, "so360", 10)) == 1

    def test_collapses_tracking_param_duplicates(self):
        rows = [
            _row("LPR连续16个月持平", "https://news.qq.com/rain/a/20260920A05HGF00?path=a&app=news"),
            _row("LPR连续16个月持平", "https://news.qq.com/rain/a/20260920A05HGF00"),
        ]
        assert len(_normalize_results(rows, "baidu", 10)) == 1

    def test_collapses_same_title_from_different_sites(self):
        rows = [
            _row("央行9月22日开展350亿元逆回购操作", "https://www.163.com/dy/article/A.html"),
            _row("央行9月22日开展350亿元逆回购操作", "https://stock.stockstar.com/B.shtml"),
        ]
        out = _normalize_results(rows, "baidu", 10)
        assert len(out) == 1
        assert out[0]["url"] == "https://www.163.com/dy/article/A.html"

    def test_preserves_engine_ranking_order(self):
        rows = [_row(f"标题{i}", f"https://x.com/{i}") for i in range(5)]
        out = _normalize_results(rows, "baidu", 3)
        assert [item["title"] for item in out] == ["标题0", "标题1", "标题2"]

    def test_truncates_overlong_fields(self):
        rows = [_row("标" * 400, "https://x.com/" + "a" * 3000, body="正文" * 500)]
        out = _normalize_results(rows, "baidu", 10)
        assert len(out[0]["title"]) == 300
        assert len(out[0]["url"]) == 2048
        assert len(out[0]["snippet"]) == 1000

    def test_collapses_whitespace_in_title_and_snippet(self):
        rows = [_row("  标题   有  空格 ", "https://x.com/a", body="摘要\n\n有\t空白")]
        out = _normalize_results(rows, "baidu", 10)
        assert out[0]["title"] == "标题 有 空格"
        assert out[0]["snippet"] == "摘要 有 空白"
