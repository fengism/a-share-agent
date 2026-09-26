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
