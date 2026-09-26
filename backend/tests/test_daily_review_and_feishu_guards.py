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
