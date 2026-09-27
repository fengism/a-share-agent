"""飞书推送图表图片链路的守卫测试。"""

from types import SimpleNamespace

from app.domain.content import ContentBlock
from app.infrastructure.integrations.feishu.adapter import (
    to_feishu_card,
    to_feishu_doc_blocks,
)
from app.infrastructure.integrations.feishu.messaging import FeishuMessageClient
from app.modules.daily_review.models import DailyReviewDataSnapshot, DailyReviewResult, DailyReviewSection
from app.modules.push.service import _attach_chart_images, _render_review_chart_pngs


def _make_review(snapshot: DailyReviewDataSnapshot | None = None) -> DailyReviewResult:
    return DailyReviewResult(
        date="2026-09-24",
        title="每日复盘",
        generated_at="2026-09-24 16:00:00",
        market_state="balanced",
        market_summary="市场震荡整理",
        index_review=DailyReviewSection(title="指数", summary="震荡", bullets=[]),
        hotspot_review=DailyReviewSection(title="热点", summary="轮动", bullets=[]),
        dragon_tiger_review=DailyReviewSection(title="龙虎榜", summary="活跃", bullets=[]),
        data_snapshot=snapshot or DailyReviewDataSnapshot(),
    )


def test_to_feishu_card_renders_image_elements():
    content = [
        ContentBlock(type="paragraph", text="市场震荡整理"),
        ContentBlock(type="image", text="市场成交额", image_key="img_v2_abc"),
        ContentBlock(type="bullet", text="策略要点：控制仓位"),
    ]
    card = to_feishu_card("daily_review", "每日复盘", content, "https://doc.example")

    images = [element for element in card["elements"] if element.get("tag") == "img"]
    assert len(images) == 1
    assert images[0]["img_key"] == "img_v2_abc"
    assert images[0]["alt"]["content"] == "市场成交额"
    # 图片位于文本之后、动作按钮之前
    tags = [element.get("tag") for element in card["elements"]]
    assert tags.index("img") < len(tags) - 1
    assert card["elements"][-1]["tag"] == "action"

    # 无 image_key 的块不应产生空图片元素
    empty = to_feishu_card("daily_review", "每日复盘", [ContentBlock(type="image", text="x")], "")
    assert not [element for element in empty["elements"] if element.get("tag") == "img"]


def test_to_feishu_doc_blocks_skip_image_blocks():
    blocks = to_feishu_doc_blocks([
        ContentBlock(type="paragraph", text="正文"),
        ContentBlock(type="image", text="图", image_key="img_v2_x"),
    ])
    assert len(blocks) == 1


def test_upload_image_posts_multipart_and_returns_key():
    calls = []

    class _FakeTransport:
        auth = SimpleNamespace(validate_settings=lambda: None)

        def post_multipart(self, url, *, data, files, error_prefix, timeout=30):
            calls.append({"url": url, "data": data, "files": files, "timeout": timeout})
            return {"code": 0, "data": {"image_key": "img_v2_test123"}}

    key = FeishuMessageClient(_FakeTransport()).upload_image(b"png-bytes")

    assert key == "img_v2_test123"
    call = calls[0]
    assert call["url"].endswith("/im/v1/images")
    assert call["data"] == {"image_type": "message"}
    assert call["files"]["image"][0] == "chart.png"
    assert call["files"]["image"][1] == b"png-bytes"
    assert call["files"]["image"][2] == "image/png"


def test_attach_chart_images_uploads_and_appends(monkeypatch):
    uploaded = []

    def fake_upload(image_bytes, **kwargs):
        if image_bytes == b"bad":
            raise RuntimeError("upload failed")
        uploaded.append(image_bytes)
        return f"img_key_{len(uploaded)}"

    monkeypatch.setattr("app.modules.push.service.feishu_client.upload_image", fake_upload)

    blocks = _attach_chart_images(
        [ContentBlock(type="heading", level=3, text="量能与市场宽度")],
        (("成交额", b"good1"), ("指数", b"bad"), ("板块", b"good2")),
    )

    images = [block for block in blocks if block.type == "image"]
    # 上传失败的图表被跳过，其余按顺序追加
    assert [block.image_key for block in images] == ["img_key_1", "img_key_2"]
    assert [block.text for block in images] == ["成交额", "板块"]
    assert blocks[0].type == "heading"


def test_render_review_chart_pngs_swallows_errors(monkeypatch):
    monkeypatch.setattr(
        "app.modules.daily_review.chart_images.render_daily_review_chart_pngs",
        lambda snapshot: (_ for _ in ()).throw(RuntimeError("browser down")),
    )
    assert _render_review_chart_pngs(_make_review()) == ()


def test_render_daily_review_chart_pngs_smoke():
    import pytest

    from app.modules.daily_review.chart_images import render_daily_review_chart_pngs

    snapshot = DailyReviewDataSnapshot(
        indices=[{"name": "上证指数", "change_pct": 0.65}],
        market_volume={
            "amount": 1.65e12,
            "amount_before_one_day": 1.75e12,
            "amount_average_60_day": 2.25e12,
        },
    )
    try:
        images = render_daily_review_chart_pngs(snapshot)
    except Exception as exc:
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc) or "libatk" in str(exc):
            pytest.skip(f"浏览器不可用，跳过图表渲染测试: {exc}")
        raise
    titles = [title for title, _ in images]
    assert "核心指数表现" in titles
    assert "市场成交额" in titles
    assert all(png.startswith(b"\x89PNG") for _, png in images)


def _make_analysis_result():
    from app.modules.analysis.models import AnalysisResult, FactorAnalysis

    return AnalysisResult(
        stock_code="600519",
        stock_name="贵州茅台",
        analysis_date="2026-09-27",
        current_price=1500.0,
        fundamental=FactorAnalysis(score=8, summary="基本面稳健"),
        technical=FactorAnalysis(score=7, summary="趋势向上", support_level=1420.0, resistance_level=1680.0),
        sentiment=FactorAnalysis(score=6, summary="情绪中性"),
        overall_rating=7,
        overall_summary="综合看多",
        estimated_price_range=(1450.0, 1650.0),
        signal="buy",
        confidence=0.8,
    )


def _fake_kline(days: int = 90):
    from datetime import date, timedelta

    from app.domain.market import KlineData, KlineItem

    base = date(2026, 6, 1)
    items = []
    price = 1400.0
    for index in range(days):
        day = base + timedelta(days=index)
        price += 1.2
        items.append(KlineItem(
            code="600519",
            date=day.isoformat(),
            open=price,
            close=price + 0.8,
            high=price + 1.5,
            low=price - 1.5,
            volume=1_000_000.0 + index,
            amount=(price + 0.8) * (1_000_000.0 + index),
        ))
    return KlineData(code="600519", period="daily", adjust="qfq", items=items)


def test_analysis_chart_cards_skip_missing_kline():
    from app.modules.analysis.chart_images import analysis_chart_cards

    cards = analysis_chart_cards(_make_analysis_result(), kline_data=None)
    titles = [title for title, _ in cards]
    # 无 K 线时价格/量价图省略，估值图仅依赖结果数据
    assert titles == ["估值与关键价位"]

    cards_with_kline = analysis_chart_cards(_make_analysis_result(), kline_data=_fake_kline())
    titles_with_kline = [title for title, _ in cards_with_kline]
    assert titles_with_kline == ["价格趋势与关键点位", "量价配合", "估值与关键价位"]
    assert all(html.strip() for _, html in cards_with_kline)


def test_render_analysis_chart_pngs_smoke():
    import pytest

    from app.modules.analysis.chart_images import render_analysis_chart_pngs

    try:
        images = render_analysis_chart_pngs(_make_analysis_result(), kline_data=_fake_kline())
    except Exception as exc:
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc) or "libatk" in str(exc):
            pytest.skip(f"浏览器不可用，跳过图表渲染测试: {exc}")
        raise
    titles = [title for title, _ in images]
    assert "价格趋势与关键点位" in titles
    assert "估值与关键价位" in titles
    assert all(png.startswith(b"\x89PNG") for _, png in images)


def test_market_end_date_handles_report_formats(monkeypatch):
    from datetime import date

    from app.modules.analysis.chart_images import _market_end_date

    monkeypatch.setattr("app.modules.analysis.chart_images.market_today", lambda: date(2026, 9, 27))
    assert _market_end_date("20260926") == date(2026, 9, 26)
    assert _market_end_date("2026-09-25") == date(2026, 9, 25)
    # 未来日期被截断到最近市场日
    assert _market_end_date("20261201") == date(2026, 9, 27)
    # 无法解析时回退到最近市场日
    assert _market_end_date("") == date(2026, 9, 27)


async def test_execute_push_request_prefetches_kline_for_analysis(monkeypatch):
    from unittest.mock import AsyncMock, Mock

    import app.modules.push.application as push_application
    from app.modules.push.schemas import PushRequest, PushResponse

    kline_mock = AsyncMock(return_value=object())
    monkeypatch.setattr("app.modules.analysis.chart_images.load_analysis_kline", kline_mock)
    execute_mock = Mock(return_value=PushResponse(success=True, target="feishu", url="", title="t"))
    monkeypatch.setattr(push_application, "execute_push", execute_mock)

    analysis_request = PushRequest(
        type="analysis", target="feishu", code="600519", date="20260927", feishu_receiver="oc_test",
    )
    await push_application.execute_push_request(analysis_request, 1)
    kline_mock.assert_awaited_once_with("600519", "20260927")
    assert execute_mock.call_args.args[2] is kline_mock.return_value

    kline_mock.reset_mock()
    review_request = PushRequest(type="daily_review", target="feishu", date="2026-09-24", feishu_receiver="oc_test")
    await push_application.execute_push_request(review_request, 1)
    kline_mock.assert_not_awaited()
    assert execute_mock.call_args.args[2] is None


def _make_chain_result(charts: list[dict]) -> object:
    from app.modules.industry_chain.models import IndustryChainChart, IndustryChainResult

    return IndustryChainResult(
        name="光模块",
        charts=[
            IndustryChainChart(title=title, description=description, type="graph", option=option)
            for title, description, option in charts
        ],
    )


def test_industry_chain_chart_cards_filter_and_cap():
    from app.modules.industry_chain.chart_images import industry_chain_chart_cards

    bar_option = {
        "xAxis": {"type": "category", "data": ["A", "B", "C"]},
        "yAxis": {"type": "value"},
        "series": [{"type": "bar", "data": [1, 2, 3]}],
    }
    result = _make_chain_result([
        ("全景图谱", "分层关系图", bar_option),
        ("空图", "无 option", {}),
        ("关系传导", "", bar_option),
        ("第四张", "", bar_option),
    ])

    cards = industry_chain_chart_cards(result)
    # 空 option 的图表被过滤，其余 3 张未超上限全部返回
    assert [title for title, _, _ in cards] == ["全景图谱", "关系传导", "第四张"]
    assert cards[0][2]["series"][0]["data"] == [1, 2, 3]

    # 默认最多 3 张
    four_charts = _make_chain_result([(f"图{i}", "", bar_option) for i in range(4)])
    assert [title for title, _, _ in industry_chain_chart_cards(four_charts)] == ["图0", "图1", "图2"]
    # 无图表时为空
    assert industry_chain_chart_cards(_make_chain_result([])) == []


def test_render_industry_chain_chart_pngs_smoke():
    import pytest

    from app.modules.industry_chain.chart_images import render_industry_chain_chart_pngs

    bar_option = {
        "xAxis": {"type": "category", "data": ["上游", "中游", "下游"]},
        "yAxis": {"type": "value"},
        "series": [{"type": "bar", "data": [3, 5, 2]}],
    }
    graph_option = {
        "series": [{
            "type": "graph", "layout": "circular",
            "data": [{"name": "上游"}, {"name": "中游"}, {"name": "下游"}],
            "links": [{"source": "上游", "target": "中游"}, {"source": "中游", "target": "下游"}],
            "label": {"show": True},
            "lineStyle": {"width": 2},
        }],
    }
    result = _make_chain_result([
        ("光模块产业链全景图谱", "分层关系图", graph_option),
        ("份额对比", "", bar_option),
    ])
    try:
        images = render_industry_chain_chart_pngs(result)
    except Exception as exc:
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc) or "libatk" in str(exc):
            pytest.skip(f"浏览器不可用，跳过图表渲染测试: {exc}")
        raise
    titles = [title for title, _ in images]
    assert "光模块产业链全景图谱" in titles
    assert "份额对比" in titles
    assert all(png.startswith(b"\x89PNG") for _, png in images)

