import pytest

from app.models.push import PushRequest
from app.services import push


def test_execute_push_to_notion_for_chat(monkeypatch):
    """execute_push should build notion content and return the created page info."""
    created = {}

    class FakeResult:
        url = "https://notion.so/doc"
        title = "Chat Title"

    monkeypatch.setattr(push, "to_notion_blocks", lambda content: [{"kind": "block", "size": len(content)}])
    monkeypatch.setattr(
        push,
        "create_page",
        lambda title, blocks: created.update({"title": title, "blocks": blocks}) or FakeResult(),
    )

    response = push.execute_push(
        PushRequest(
            target="notion",
            type="chat",
            chat_title="Chat Title",
            chat_content="# Hello",
        )
    )

    assert response.success is True
    assert response.target == "notion"
    assert response.url == "https://notion.so/doc"
    assert created["title"] == "Chat Title"
    assert created["blocks"][0]["kind"] == "block"


def test_execute_push_to_feishu_chat_uses_default_receiver(monkeypatch):
    """execute_push should fall back to the default feishu receiver for chat pushes."""
    sent = {}

    class FakeSettings:
        feishu_default_receiver = "ou_default"

    monkeypatch.setattr(push, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(push, "to_feishu_card", lambda push_type, title, content, url: {"title": title, "url": url})
    monkeypatch.setattr(push, "send_card", lambda receiver, card: sent.update({"receiver": receiver, "card": card}))

    response = push.execute_push(
        PushRequest(
            target="feishu",
            type="chat",
            chat_title="Chat Title",
            chat_content="hello",
        )
    )

    assert response.success is True
    assert response.message == "已推送到 ou_default"
    assert sent["receiver"] == "ou_default"
    assert sent["card"]["title"] == "Chat Title"


def test_execute_push_analysis_without_data_raises_lookup(monkeypatch):
    """execute_push should raise LookupError when the requested analysis is missing."""
    monkeypatch.setattr(push, "get_latest_analysis", lambda code: None)

    with pytest.raises(LookupError, match="暂无分析结果，请先生成"):
        push.execute_push(PushRequest(target="notion", type="analysis", code="600519"))
