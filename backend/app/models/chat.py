from pydantic import BaseModel


class ToolCallFunction(BaseModel):
    """Purpose: 工具调用中的函数名称和参数。"""
    name: str
    arguments: str  # JSON string


class ToolCallInfo(BaseModel):
    """Purpose: LLM 返回的工具调用信息（OpenAI function-calling 格式）。"""
    id: str
    type: str = "function"
    function: ToolCallFunction


class ToolResultInfo(BaseModel):
    """Purpose: 工具执行后的结果反馈。"""
    tool_call_id: str
    name: str
    content: str  # JSON string or error message
    is_error: bool = False


class ChatMessage(BaseModel):
    """Purpose: 对话历史中单条消息，支持 user/assistant/tool 三种角色。"""
    role: str  # "user" | "assistant" | "tool"
    content: str | None = None
    tool_calls: list[ToolCallInfo] | None = None
    tool_call_id: str | None = None  # when role == "tool"
    name: str | None = None
    reasoning_content: str | None = None  # DeepSeek thinking mode


class ChatRequest(BaseModel):
    """Purpose: 聊天接口的请求体。"""
    message: str
    history: list[ChatMessage] | None = None


class ChatStreamDelta(BaseModel):
    """Purpose: 聊天流式响应的单个增量事件，支持文本/推理/工具调用/工具结果等。"""
    type: str  # "text" | "reasoning" | "tool_call" | "tool_result" | "error" | "done"
    content: str | None = None
    tool_call: ToolCallInfo | None = None
    tool_result: ToolResultInfo | None = None
    error: str | None = None
    reasoning_content: str | None = None  # DeepSeek thinking mode
