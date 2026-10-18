"""推送分发中枢单元测试：签名算法、卡片/Markdown 组装、多通道发送与测试端点。"""

from __future__ import annotations

import base64
import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes.push import get_notification_channel_status, trigger_channel_test_webhook
from app.configuration.schema import Settings
from app.domain.identity import AuthenticatedUser
from app.modules.daily_review.models import (
    DailyReviewDataSnapshot,
    DailyReviewResult,
    DailyReviewSection,
    DailyReviewSentimentCycle,
    DailyReviewWatchItem,
)
from app.modules.potential.schemas import PotentialDailyResult, PotentialStockItem
from app.modules.push.dispatcher import (
    compute_feishu_sign,
    dispatch_daily_review_notification,
    dispatch_potential_stocks_notification,
    format_daily_review_feishu_card,
    format_daily_review_wecom_markdown,
    format_potential_stocks_feishu_card,
    format_potential_stocks_wecom_markdown,
    send_feishu_webhook,
    send_test_notification,
    send_wecom_webhook,
    send_wxpusher,
)
from app.modules.push.schemas import TestWebhookRequest


@pytest.fixture
def mock_user() -> AuthenticatedUser:
    return {"id": 1, "username": "testuser", "is_active": True}


@pytest.fixture
def sample_daily_review() -> DailyReviewResult:
    return DailyReviewResult(
        date="2026-10-15",
        title="2026-10-15 每日复盘",
        generated_at="2026-10-15T15:30:00",
        market_state="attack",
        position_range="6-8成",
        market_summary="今日大盘缩量震荡走高，科技题材全线反弹，情绪回暖显著。",
        sentiment_cycle=DailyReviewSentimentCycle(stage="主升共振", score=78.5),
        index_review=DailyReviewSection(title="指数走势", summary="三大指数集体翻红"),
        hotspot_review=DailyReviewSection(title="热点题材", summary="半导体领涨"),
        dragon_tiger_review=DailyReviewSection(title="龙虎榜", summary="机构持续净买入"),
        next_day_watchlist=[
            DailyReviewWatchItem(name="中芯国际", code="688981", role="中军容量票", trigger="高开站稳均线", reason="半导体自主可控"),
            DailyReviewWatchItem(name="海光信息", code="688041", role="总龙头", trigger="早盘快速封板", reason="AI芯片需求激增"),
        ],
        data_snapshot=DailyReviewDataSnapshot(
            indices=[
                {"name": "上证指数", "change_pct": 1.25},
                {"name": "深证成指", "change_pct": 1.80},
                {"name": "创业板指", "change_pct": 2.45},
            ],
            top_sectors=[
                {"name": "半导体", "change_pct": 4.5},
                {"name": "人工智能", "change_pct": 3.8},
            ],
        ),
    )


@pytest.fixture
def sample_potential_result() -> PotentialDailyResult:
    return PotentialDailyResult(
        date="2026-10-15",
        generated_at="2026-10-15T16:00:00",
        universe_size=5200,
        evaluated=5180,
        failed_count=20,
        market_regime="bear",
        market_note="沪深300跌破MA20",
        market_emotion="strong",
        items=[
            PotentialStockItem(
                code="000001",
                name="平安银行",
                price=12.5,
                change_pct=3.2,
                turnover_pct=2.1,
                amount=500000000,
                industry="银行",
                score=88.5,
                strategies=["成交量突增", "均线多头"],
                signal_date="2026-10-15",
                signal_age_days=0,
                fundamental_score=0.5,
                theme_score=0.5,
                themes=["低空经济"],
                risk_flags=["RSI超买"],
            ),
            PotentialStockItem(
                code="600519",
                name="贵州茅台",
                price=1680.0,
                change_pct=1.5,
                turnover_pct=0.8,
                amount=3500000000,
                score=85.0,
                strategies=["价值白马突破"],
                signal_date="2026-10-15",
                signal_age_days=0,
            ),
        ],
    )


def test_compute_feishu_sign():
    secret = "test_secret_key"
    timestamp = 1600000000
    sign = compute_feishu_sign(secret, timestamp)
    expected_hmac = hmac.new(
        f"{timestamp}\n{secret}".encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    expected_sign = base64.b64encode(expected_hmac).decode("utf-8")
    assert sign == expected_sign


@pytest.mark.asyncio
async def test_send_feishu_webhook_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"code": 0, "msg": "success"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        ok, msg = await send_feishu_webhook(
            "https://open.feishu.cn/open-apis/bot/v2/hook/abc",
            {"header": {}, "elements": []},
            secret="my_secret",
        )
        assert ok is True
        assert "送达" in msg
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert "timestamp" in call_kwargs["json"]
        assert "sign" in call_kwargs["json"]
        assert call_kwargs["json"]["msg_type"] == "interactive"


@pytest.mark.asyncio
async def test_send_feishu_webhook_failure():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"code": 19001, "msg": "sign match fail"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        ok, msg = await send_feishu_webhook(
            "https://open.feishu.cn/open-apis/bot/v2/hook/abc",
            {"header": {}},
        )
        assert ok is False
        assert "sign match fail" in msg


@pytest.mark.asyncio
async def test_send_wecom_webhook():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        ok, msg = await send_wecom_webhook("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc", "## 测试内容")
        assert ok is True
        assert "送达" in msg


@pytest.mark.asyncio
async def test_send_wxpusher():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"code": 1000, "msg": "处理成功"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        ok, msg = await send_wxpusher(
            app_token="AT_testtoken",
            uids=["UID_123"],
            title="复盘通知",
            content_markdown="## 标题",
        )
        assert ok is True
        assert "已发送" in msg


def test_format_daily_review_feishu_card(sample_daily_review: DailyReviewResult):
    card = format_daily_review_feishu_card(sample_daily_review)
    assert card["config"]["wide_screen_mode"] is True
    assert "2026-10-15" in card["header"]["title"]["content"]
    assert len(card["elements"]) >= 2
    content_text = card["elements"][0]["text"]["content"]
    assert "**上证指数**: +1.25%" in content_text
    assert "进攻" in content_text
    assert "半导体" in content_text
    watchlist_text = card["elements"][2]["text"]["content"]
    assert "中芯国际" in watchlist_text


def test_format_daily_review_wecom_markdown(sample_daily_review: DailyReviewResult):
    md = format_daily_review_wecom_markdown(sample_daily_review)
    assert "### 📈 A股每日收盘复盘 · 2026-10-15" in md
    assert "上证指数 +1.25%" in md
    assert "半导体" in md
    assert "中芯国际" in md


def test_format_potential_stocks_feishu_card(sample_potential_result: PotentialDailyResult):
    card = format_potential_stocks_feishu_card(sample_potential_result)
    assert "2026-10-15" in card["header"]["title"]["content"]
    content_text = card["elements"][0]["text"]["content"]
    assert "平安银行" in content_text
    assert "成交量突增" in content_text
    assert "银行" in content_text
    assert "RSI超买" in content_text
    assert "基本面" in content_text
    assert "低空经济" in content_text
    assert "市场环境" in content_text
    assert "情绪" in content_text


def test_format_potential_stocks_wecom_markdown(sample_potential_result: PotentialDailyResult):
    md = format_potential_stocks_wecom_markdown(sample_potential_result)
    assert "### ⚡ 题材挖掘与潜力个股雷达 · 2026-10-15" in md
    assert "平安银行" in md
    assert "88.5" in md
    assert "银行" in md
    assert "基本面" in md
    assert "低空经济" in md
    assert "市场环境" in md
    assert "情绪" in md


@pytest.mark.asyncio
async def test_dispatch_daily_review_notification_disabled(sample_daily_review: DailyReviewResult, monkeypatch):
    test_settings = Settings(push_auto_enabled=False)
    monkeypatch.setattr("app.modules.push.dispatcher.get_effective_settings", lambda: test_settings)

    results = await dispatch_daily_review_notification(sample_daily_review)
    assert results == {}


@pytest.mark.asyncio
async def test_dispatch_daily_review_notification_enabled(sample_daily_review: DailyReviewResult, monkeypatch):
    test_settings = Settings(
        push_auto_enabled=True,
        push_daily_review_auto=True,
        feishu_webhook_url="https://feishu.example/hook",
        wecom_webhook_url="https://wecom.example/hook",
    )
    monkeypatch.setattr("app.modules.push.dispatcher.get_effective_settings", lambda: test_settings)

    with patch("app.modules.push.channels.feishu.FeishuChannel._post_payload", return_value=(True, "ok")) as mock_feishu, \
         patch("app.modules.push.channels.wecom.WecomChannel._post_markdown", return_value=(True, "ok")) as mock_wecom:
        results = await dispatch_daily_review_notification(sample_daily_review)
        assert results["feishu"] == "成功"
        assert results["wecom"] == "成功"
        mock_feishu.assert_called_once()
        mock_wecom.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_potential_stocks_notification_enabled(sample_potential_result: PotentialDailyResult, monkeypatch):
    test_settings = Settings(
        push_auto_enabled=True,
        push_potential_auto=True,
        wecom_webhook_url="https://wecom.example/hook",
    )
    monkeypatch.setattr("app.modules.push.dispatcher.get_effective_settings", lambda: test_settings)

    with patch("app.modules.push.channels.wecom.WecomChannel._post_markdown", return_value=(True, "ok")) as mock_wecom:
        results = await dispatch_potential_stocks_notification(sample_potential_result)
        assert results["wecom"] == "成功"
        mock_wecom.assert_called_once()


@pytest.mark.asyncio
async def test_send_test_notification():
    with patch("app.modules.push.channels.feishu.FeishuChannel._post_payload", return_value=(True, "ok")) as mock_feishu:
        ok, msg = await send_test_notification("feishu", webhook_url="https://feishu.test/hook")
        assert ok is True
        mock_feishu.assert_called_once()

    ok, msg = await send_test_notification("unknown_channel")
    assert ok is False
    assert "不支持" in msg


@pytest.mark.asyncio
async def test_api_routes(mock_user: AuthenticatedUser, monkeypatch):
    test_settings = Settings(
        push_auto_enabled=True,
        push_daily_review_auto=True,
        feishu_webhook_url="https://feishu.test/hook",
    )
    monkeypatch.setattr("app.configuration.get_effective_settings", lambda: test_settings)

    status = await get_notification_channel_status(_user=mock_user)
    assert status.feishu_configured is True
    assert status.wecom_configured is False
    assert status.auto_enabled is True
    assert status.daily_review_auto is True

    with patch("app.api.routes.push.send_test_notification", return_value=(True, "消息已送达")) as mock_test:
        resp = await trigger_channel_test_webhook(
            TestWebhookRequest(channel="feishu", webhook_url="https://feishu.test/hook"),
            _user=mock_user,
        )
        assert resp.success is True
        assert resp.channel == "feishu"
        mock_test.assert_called_once()


def test_channel_registry():
    from app.modules.push.channels.registry import create_default_registry

    reg = create_default_registry()
    channels = reg.list_all()
    assert len(channels) >= 3
    assert reg.get("feishu") is not None
    assert reg.get("wecom") is not None
    assert reg.get("wxpusher") is not None

    test_settings = Settings(feishu_webhook_url="https://feishu.example/hook")
    active = reg.get_active(test_settings)
    assert len(active) == 1
    assert active[0].channel_id == "feishu"


@pytest.mark.asyncio
async def test_event_bus_and_subscribers(sample_daily_review: DailyReviewResult, monkeypatch):
    import asyncio

    from app.core.events import event_bus
    from app.modules.push.subscribers import register_push_subscribers

    register_push_subscribers()

    with patch("app.modules.push.subscribers.dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
        mock_dispatch.return_value = {"feishu": "成功"}

        await event_bus.publish(sample_daily_review, name="daily_review.completed")
        await asyncio.sleep(0.05)  # 等待后台任务执行完成

        mock_dispatch.assert_called_once()
        called_msg = mock_dispatch.call_args[0][0]
        assert called_msg.category == "daily_review"
        assert "2026-10-15" in called_msg.title


@pytest.mark.asyncio
async def test_dispatch_debounce_and_history(sample_daily_review: DailyReviewResult, monkeypatch):
    from app.api.routes.push import get_notification_history
    from app.modules.push.dispatcher import _recent_dispatches

    _recent_dispatches.clear()
    test_settings = Settings(
        push_auto_enabled=True,
        push_daily_review_auto=True,
        feishu_webhook_url="https://feishu.example/hook",
    )
    monkeypatch.setattr("app.modules.push.dispatcher.get_effective_settings", lambda: test_settings)

    with patch("app.modules.push.channels.feishu.FeishuChannel._post_payload", return_value=(True, "ok")) as mock_feishu:
        res1 = await dispatch_daily_review_notification(sample_daily_review)
        assert res1["feishu"] == "成功"
        assert mock_feishu.call_count == 1

        # 第二次调用触发防抖
        res2 = await dispatch_daily_review_notification(sample_daily_review)
        assert res2.get("debounce") == "已防抖跳过"
        assert mock_feishu.call_count == 1

        # 检查审计历史接口
        history = await get_notification_history(limit=5, _user={"id": 1, "username": "admin", "is_active": True})
        assert len(history) >= 1
        assert history[0]["category"] == "daily_review"


def test_compute_dingtalk_sign():
    import urllib.parse

    from app.modules.push.channels.dingtalk import compute_dingtalk_sign

    secret = "SEC123456"
    timestamp = 1600000000000
    sign = compute_dingtalk_sign(secret, timestamp)

    expected_hmac = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}\n{secret}".encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    expected_sign = urllib.parse.quote_plus(base64.b64encode(expected_hmac).decode("utf-8"))
    assert sign == expected_sign


@pytest.mark.asyncio
async def test_send_dingtalk_webhook():
    from app.modules.push.dispatcher import send_dingtalk_webhook

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}

    with patch("app.modules.push.channels.dingtalk.resilient_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        ok, msg = await send_dingtalk_webhook(
            "https://oapi.dingtalk.com/robot/send?access_token=token123",
            title="复盘通知",
            markdown_text="## 测试内容",
            secret="SEC_test",
        )
        assert ok is True
        assert "送达" in msg
        mock_post.assert_called_once()
        target_url = mock_post.call_args[0][0]
        assert "timestamp=" in target_url
        assert "sign=" in target_url


@pytest.mark.asyncio
async def test_resilient_post_retry():
    from app.modules.push.channels.http_client import resilient_post

    # 第一次 502，第二次 200
    resp_502 = MagicMock()
    resp_502.status_code = 502
    resp_502.headers = {}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.headers = {}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [resp_502, resp_200]
        res = await resilient_post("https://test.hook", json_data={"a": 1}, base_backoff=0.01)
        assert res.status_code == 200
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_channel_individual_toggle_and_category_filtering(sample_daily_review: DailyReviewResult, monkeypatch):
    from app.modules.push.channels.registry import create_default_registry

    reg = create_default_registry()
    # 模拟飞书、钉钉均配置了 URL，但飞书被单独关闭 (push_feishu_enabled=False)
    settings = Settings(
        feishu_webhook_url="https://feishu.example/hook",
        push_feishu_enabled=False,
        dingtalk_webhook_url="https://dingtalk.example/hook",
        push_dingtalk_enabled=True,
    )

    active = reg.get_active(settings)
    active_ids = [c.channel_id for c in active]
    assert "feishu" not in active_ids
    assert "dingtalk" in active_ids


@pytest.mark.asyncio
async def test_clear_notification_history_api(mock_user: AuthenticatedUser):
    from app.api.routes.push import clear_notification_history_records, get_notification_history
    from app.infrastructure.persistence.notification_history import record_notification_delivery

    record_notification_delivery("daily_review", "测试标题", "摘要", "info", {})
    records_before = await get_notification_history(limit=5, _user=mock_user)
    assert len(records_before) >= 1

    del_res = await clear_notification_history_records(_user=mock_user)
    assert del_res["success"] is True

    records_after = await get_notification_history(limit=5, _user=mock_user)
    assert len(records_after) == 0


def test_format_system_alert():
    from app.modules.push.domain.message import NotificationSeverity
    from app.modules.push.formatters.system_alert import format_system_alert

    msg = format_system_alert(
        title="大盘突发跳水预警",
        content_markdown="上证指数 5 分钟内快速下跌超过 1%",
        severity=NotificationSeverity.ALERT,
    )
    assert "🚨 大盘突发跳水预警" in msg.title
    assert msg.category == "system_alert"
    assert msg.severity == NotificationSeverity.ALERT



