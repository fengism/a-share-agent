"""配置脱敏守卫：推送 Webhook 与飞书目录 Token 不得明文下发。"""

from __future__ import annotations

from app.api.routes.settings import _to_response
from app.configuration import SECRET_KEYS, Settings
from app.configuration.api_models import CONFIG_VALUE_FIELDS


def test_webhook_and_folder_tokens_are_registered_as_secrets() -> None:
    """这些字段携带 bearer 凭证，必须进入 SECRET_KEYS 才会在接口层脱敏。"""
    for key in (
        "feishu_webhook_url",
        "dingtalk_webhook_url",
        "wecom_webhook_url",
        "feishu_folder_token",
    ):
        assert key in CONFIG_VALUE_FIELDS
        assert key in SECRET_KEYS


def test_config_response_masks_webhook_and_folder_token() -> None:
    settings = Settings(
        feishu_webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/abcdef1234567890",
        dingtalk_webhook_url="https://oapi.dingtalk.com/robot/send?access_token=secret-value-123",
        wecom_webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=wecom-secret-key",
        feishu_folder_token="fldcnABCDEFGHIJK",
    )

    response = _to_response(settings, is_admin=True)

    assert "***" in (response.feishu_webhook_url or "")
    assert "***" in (response.dingtalk_webhook_url or "")
    assert "***" in (response.wecom_webhook_url or "")
    assert "***" in (response.feishu_folder_token or "")
    assert "abcdef1234567890" not in (response.feishu_webhook_url or "")
    assert "secret-value-123" not in (response.dingtalk_webhook_url or "")
    assert "wecom-secret-key" not in (response.wecom_webhook_url or "")
    assert "fldcnABCDEFGHIJK" not in (response.feishu_folder_token or "")
