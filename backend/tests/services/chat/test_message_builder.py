from app.models.chat import ChatMessage, ToolCallFunction, ToolCallInfo
from app.services.chat.message_builder import build_messages


def test_build_messages_with_empty_history():
    """build_messages emits a system prompt and the user query when history is empty."""
    messages = build_messages("你好", None, 20)

    assert messages[-1] == {"role": "user", "content": "你好"}
    assert messages[0]["role"] == "system"


def test_build_messages_skips_duplicate_latest_user_message():
    """build_messages drops a trailing user message that duplicates the new query."""
    history = [ChatMessage(role="user", content="PE小于20的白酒股")]

    messages = build_messages("PE小于20的白酒股", history, 20)

    user_messages = [m for m in messages if m["role"] == "user"]
    assert user_messages == [{"role": "user", "content": "PE小于20的白酒股"}]


def test_build_messages_preserves_tool_call_history():
    """build_messages keeps assistant tool_calls and corresponding tool result messages."""
    tool_call = ToolCallInfo(
        id="call_1",
        type="function",
        function=ToolCallFunction(name="search_stocks", arguments='{"query":"茅台"}'),
    )
    history = [
        ChatMessage(role="assistant", content=None, tool_calls=[tool_call]),
        ChatMessage(role="tool", tool_call_id="call_1", content="[]"),
    ]

    messages = build_messages("继续", history, 20)

    assistant = messages[1]
    tool = messages[2]
    assert assistant["role"] == "assistant"
    assert assistant["tool_calls"][0]["function"]["name"] == "search_stocks"
    assert tool == {"role": "tool", "tool_call_id": "call_1", "content": "[]"}
