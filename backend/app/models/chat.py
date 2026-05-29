from pydantic import BaseModel


class ToolCallFunction(BaseModel):
    name: str
    arguments: str  # JSON string


class ToolCallInfo(BaseModel):
    id: str
    type: str = "function"
    function: ToolCallFunction


class ToolResultInfo(BaseModel):
    tool_call_id: str
    name: str
    content: str  # JSON string or error message
    is_error: bool = False


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "tool"
    content: str | None = None
    tool_calls: list[ToolCallInfo] | None = None
    tool_call_id: str | None = None  # when role == "tool"
    name: str | None = None
    reasoning_content: str | None = None  # DeepSeek thinking mode


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] | None = None


class ChatStreamDelta(BaseModel):
    type: str  # "text" | "reasoning" | "tool_call" | "tool_result" | "error" | "done"
    content: str | None = None
    tool_call: ToolCallInfo | None = None
    tool_result: ToolResultInfo | None = None
    error: str | None = None
    reasoning_content: str | None = None  # DeepSeek thinking mode
