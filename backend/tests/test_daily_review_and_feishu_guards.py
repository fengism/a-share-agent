"""每日复盘 Prompt 输出截断容错与飞书文档权限参数守卫测试。"""

from unittest.mock import MagicMock

from app.infrastructure.integrations.feishu.documents import FeishuDocumentClient
from app.modules.daily_review.models import DailyReviewSection
from app.modules.daily_review.prompts import DailyReviewPromptOutput


class TestDailyReviewPromptOutputTruncation:
    def _base_payload(self) -> dict:
        return {
            "market_state": "balanced",
            "market_summary": "今日市场震荡整理",
            "index_review": DailyReviewSection(title="指数", summary="三大指数小幅波动", bullets=[]),
            "hotspot_review": DailyReviewSection(title="热点", summary="科技板块活跃", bullets=[]),
            "dragon_tiger_review": DailyReviewSection(title="龙虎榜", summary="机构买入居多", bullets=[]),
        }

    def test_truncates_invalid_conditions_when_over_limit(self):
        payload = self._base_payload()
        payload["invalid_conditions"] = [f"条件 {i}" for i in range(1, 8)]  # 7 items, limit is 6

        output = DailyReviewPromptOutput.model_validate(payload)
        assert len(output.invalid_conditions) == 6
        assert output.invalid_conditions == [f"条件 {i}" for i in range(1, 7)]

    def test_truncates_all_six_item_lists(self):
        payload = self._base_payload()
        payload["risk_alerts"] = [f"风险 {i}" for i in range(10)]
        payload["opportunities"] = [f"机会 {i}" for i in range(8)]
        payload["strategy_notes"] = [f"策略 {i}" for i in range(7)]

        output = DailyReviewPromptOutput.model_validate(payload)
        assert len(output.risk_alerts) == 6
        assert len(output.opportunities) == 6
        assert len(output.strategy_notes) == 6

    def test_truncates_data_gaps_when_over_twelve(self):
        payload = self._base_payload()
        payload["data_gaps"] = [f"缺失 {i}" for i in range(15)]  # 15 items, limit is 12

        output = DailyReviewPromptOutput.model_validate(payload)
        assert len(output.data_gaps) == 12

    def test_preserves_valid_lengths(self):
        payload = self._base_payload()
        payload["invalid_conditions"] = ["条件 1", "条件 2"]
        payload["risk_alerts"] = ["风险 1"]

        output = DailyReviewPromptOutput.model_validate(payload)
        assert output.invalid_conditions == ["条件 1", "条件 2"]
        assert output.risk_alerts == ["风险 1"]


class TestFeishuDocumentPermission:
    def test_grant_doc_edit_permission_chat_id_uses_openchat(self):
        transport = MagicMock()
        mock_response = MagicMock()
        transport.post.return_value = mock_response
        transport.parse_response.return_value = {"code": 0}

        client = FeishuDocumentClient(transport, sleep=lambda _: None)
        client.grant_doc_edit_permission(
            doc_id="doc123",
            receiver="oc_8989488fbb32762827ff8139c1a21238",
            doc_type="docx",
        )

        transport.post.assert_called_once()
        args, kwargs = transport.post.call_args
        assert kwargs["json"]["member_type"] == "openchat"
        assert kwargs["json"]["member_id"] == "oc_8989488fbb32762827ff8139c1a21238"

    def test_grant_doc_edit_permission_user_uses_openid(self):
        transport = MagicMock()
        mock_response = MagicMock()
        transport.post.return_value = mock_response
        transport.parse_response.return_value = {"code": 0}

        client = FeishuDocumentClient(transport, sleep=lambda _: None)
        client.grant_doc_edit_permission(
            doc_id="doc123",
            receiver="ou_1234567890abcdef",
            doc_type="wiki",
        )

        transport.post.assert_called_once()
        args, kwargs = transport.post.call_args
        assert kwargs["json"]["member_type"] == "openid"
        assert kwargs["json"]["member_id"] == "ou_1234567890abcdef"
        assert kwargs["params"]["type"] == "wiki"


class TestDailyReviewPushDataBoard:
    def test_build_daily_review_includes_structured_data_board(self):
        from app.infrastructure.integrations.feishu.adapter import to_feishu_card, to_feishu_doc_blocks
        from app.modules.daily_review.models import DailyReviewDataSnapshot, DailyReviewResult
        from app.modules.push.content import build_content

        snapshot = DailyReviewDataSnapshot(
            indices=[
                {"name": "上证指数", "price": 3080.5, "change_pct": 0.85, "amount": 450000000000},
                {"name": "深证成指", "price": 10500.0, "change_pct": 1.20, "amount": 550000000000},
            ],
            market_volume={"amount": 1000000000000, "amount_before_one_day": 950000000000},
            market_statistics={
                "up_count": 3200,
                "down_count": 1600,
                "flat_count": 150,
                "limit_up_count": 65,
                "limit_down_count": 5,
            },
            top_sectors=[
                {"name": "半导体", "change_pct": 3.85, "leading_stock": "中芯国际", "leading_change_pct": 6.5},
            ],
            bottom_sectors=[
                {"name": "煤炭开采", "change_pct": -2.10, "leading_stock": "中国神华", "leading_change_pct": -3.2},
            ],
            dragon_tiger=[
                {"name": "拓维信息", "code": "002261", "net_amount": 152000000, "change_pct": 9.98},
            ],
            hot_concepts=[
                {"name": "华为昇腾"},
                {"name": "CPO"},
            ],
        )
        review = DailyReviewResult(
            date="2026-09-24",
            title="每日复盘 - 2026-09-24",
            generated_at="2026-09-24 16:00:00",
            market_state="attack",
            position_range="5-7成",
            market_summary="两市成交突破万亿，科技主线强势领涨。",
            llm_review="## 今日大盘复盘\n\n大盘今日放量大涨，主线明确。\n\n### 明日交易计划\n\n- 建议仓位：5-7成\n- 保持进攻节奏",
            index_review=DailyReviewSection(title="指数", summary="放量反弹", bullets=[]),
            hotspot_review=DailyReviewSection(title="热点", summary="科技爆发", bullets=[]),
            dragon_tiger_review=DailyReviewSection(title="龙虎榜", summary="机构大举买入", bullets=[]),
            data_snapshot=snapshot,
        )

        blocks = build_content("daily_review", review)
        texts = [b.text for b in blocks]

        # 验证包含数据看板
        assert any("核心市场数据看板" in t for t in texts)
        assert any("上证指数" in t and "+0.85%" in t for t in texts)
        assert any("两市总成交额" in t and "10000.00 亿元" in t for t in texts)
        assert any("上涨 3200 家" in t and "下跌 1600 家" in t for t in texts)
        assert any("半导体" in t and "中芯国际" in t for t in texts)
        assert any("拓维信息" in t and "1.52 亿元" in t for t in texts)
        assert any("华为昇腾" in t for t in texts)

        # 验证可转为飞书文档块
        doc_blocks = to_feishu_doc_blocks(blocks)
        assert len(doc_blocks) > 10

        # 验证飞书卡片策略提取正确
        card = to_feishu_card("daily_review", "2026-09-24 复盘", blocks, "https://feishu.cn/docx/123")
        card_content = str(card)
        assert "两市成交突破万亿" in card_content
        assert "5-7成" in card_content


class TestDailyReviewDepthOptimization:
    async def test_historical_indices_calculates_change_pct_and_amplitude_when_none(self, monkeypatch):
        from datetime import date
        from unittest.mock import AsyncMock
        from app.domain.market import KlineData, KlineItem
        from app.modules.daily_review.collector import _historical_indices

        mock_item = KlineItem(
            date="2026-09-24",
            open=2910.0,
            close=3000.0,
            high=3020.0,
            low=2905.0,
            volume=100000,
            amount=250000000000,
            pre_close=2900.0,
            change_pct=None,
            amplitude=None,
        )
        mock_response = KlineData(
            code="000001",
            period="daily",
            adjust="",
            items=[mock_item],
            source="test_source",
        )
        monkeypatch.setattr(
            "app.modules.daily_review.collector.get_index_kline",
            AsyncMock(return_value=mock_response),
        )

        res = await _historical_indices(date(2026, 9, 24))
        assert len(res.indices) == 4
        item = res.indices[0]
        # (3000 - 2900) / 2900 * 100 = 3.45
        assert item.change_pct == 3.45
        # (3020 - 2905) / 2900 * 100 = 3.97
        assert item.amplitude == 3.97

    def test_review_builder_enriches_market_summary_with_limit_pools_and_distribution(self):
        from app.modules.daily_review.models import DailyReviewDataSnapshot
        from app.modules.daily_review.review_builder import _market_summary

        snapshot = DailyReviewDataSnapshot(
            indices=[{"name": "上证指数", "price": 3000.0, "change_pct": 1.5}],
            market_statistics={
                "up_count": 3500,
                "down_count": 1200,
                "flat_count": 100,
                "limit_up_count": 58,
                "limit_down_count": 3,
                "limit_up_stocks": [
                    {"name": "常山北明", "board_count": 3, "sector_name": "华为概念"},
                    {"name": "深圳华强", "board_count": 1, "sector_name": "电子元器件"},
                ],
                "limit_down_stocks": [
                    {"name": "大连重工", "sector_name": "高端装备"},
                ],
                "stock_pct_distribution": [
                    {"label": ">7", "count": 120},
                    {"label": "0~3", "count": 2200},
                ],
            },
        )
        summary = _market_summary(snapshot, "当日共整理")
        assert "全市场上涨 3500 家" in summary
        assert "涨停 58 家" in summary
        assert "常山北明(3板[华为概念])" in summary
        assert "深圳华强(首板[电子元器件])" in summary
        assert "大连重工[高端装备]" in summary
        assert ">7%: 120家" in summary

    def test_build_prompt_formats_readable_kline_and_sectors(self):
        from app.modules.daily_review.models import DailyReviewDataSnapshot
        from app.modules.daily_review.review_builder import build_prompt

        snapshot = DailyReviewDataSnapshot(
            indices=[
                {
                    "name": "上证指数",
                    "code": "000001",
                    "price": 3050.25,
                    "change_pct": 1.25,
                    "amount": 420000000000,
                    "open": 3010.0,
                    "high": 3060.0,
                    "low": 3005.0,
                    "pre_close": 3012.5,
                    "amplitude": 1.83,
                }
            ],
            top_sectors=[
                {"name": "半导体", "change_pct": 4.2, "leading_stock": "中芯国际", "leading_change_pct": 7.5}
            ],
            bottom_sectors=[
                {"name": "煤炭", "change_pct": -1.5, "leading_stock": "中国神华", "leading_change_pct": -2.0}
            ],
            dragon_tiger=[
                {"name": "拓维信息", "code": "002261", "net_amount": 150000000, "change_pct": 10.0, "reason": "日涨幅偏离值达7%", "turnover_pct": 15.2}
            ],
        )
        template = "INDICES:\n{indices_placeholder}\nSECTORS:\n{top_sectors_placeholder}\nDRAGON:\n{dragon_tiger_placeholder}\n{market_statistics_placeholder}\n{bottom_sectors_placeholder}\n{hot_concepts_placeholder}\n{hot_industries_placeholder}\n{hot_stocks_placeholder}\n{news_placeholder}\n{market_volume_placeholder}\n{macro_data_placeholder}\n{source_status_placeholder}\n{date}"
        prompt = build_prompt("2026-09-24", snapshot, template)
        assert "上证指数(000001)：收盘 3050.25，涨跌幅 +1.25%，成交额 4200.0亿元" in prompt
        assert "今开:3010.0" in prompt
        assert "最高:3060.0" in prompt
        assert "半导体：涨跌幅 4.2%，领涨股 中芯国际(7.5%)" in prompt
        assert "拓维信息(002261)：净买入 15000.0万元，涨跌幅 10.0%，换手率 15.2%，上榜原因：日涨幅偏离值达7%" in prompt

    def test_report_renderer_produces_clean_report_without_technical_errors(self):
        from app.modules.daily_review.models import DailyReviewDataSnapshot, DailyReviewResult, DailyReviewSection, DailyReviewSourceStatus
        from app.modules.daily_review.report_renderer import render_daily_review_markdown

        snapshot = DailyReviewDataSnapshot(
            source_status={
                "hot_stocks": DailyReviewSourceStatus(status="unavailable", error="热门股票不支持历史回溯，未使用当前数据替代"),
                "indices": DailyReviewSourceStatus(status="complete"),
            }
        )
        result = DailyReviewResult(
            date="2026-09-24",
            title="2026-09-24 每日复盘",
            generated_at="2026-09-24 16:30:00",
            market_state="attack",
            position_range="6~7成进攻",
            market_summary="两市放量突破，科技主线领涨。",
            index_review=DailyReviewSection(title="指数与量价格局", summary="放量突破长阳线", bullets=["上证指数突破3000点整数关口"]),
            hotspot_review=DailyReviewSection(title="板块轮动与题材生命周期", summary="科技主线加速", bullets=["半导体启动主升浪"]),
            dragon_tiger_review=DailyReviewSection(title="情绪周期与资金微观动向", summary="游资与机构共振", bullets=["拓维信息机构大幅加仓"]),
            opportunities=["低吸半导体设备龙头"],
            risk_alerts=["警惕次日分时冲高回落"],
            strategy_notes=["建议仓位6~7成", "超预期：早盘若放量高开则持股待涨"],
            invalid_conditions=["若早盘竞价大幅低开且跌停个股超20家"],
            data_gaps=["历史热点个股排行与实时新闻未覆盖"],
            data_snapshot=snapshot,
        )

        md = render_daily_review_markdown(result)
        assert "# 2026-09-24 每日市场复盘" in md
        assert "## 今日大盘复盘" in md
        assert "进攻型（多头主导/放量突破）" in md
        assert "建议仓位：6~7成进攻" in md
        assert "### 1. 指数与量价格局" in md
        assert "### 2. 板块轮动与题材生命周期" in md
        assert "### 3. 情绪周期与资金微观动向" in md
        assert "### 6. 明日交易计划与情景推演" in md
        assert "## 数据覆盖与核验状态" in md
        assert "历史热点个股排行与实时新闻未覆盖" in md
        assert "热门股票不支持历史回溯，未使用当前数据替代" not in md

