export interface ToolCallFunction {
  name: string;
  arguments: string;
}

export interface ToolCallInfo {
  id: string;
  type: string;
  function: ToolCallFunction;
}

export interface ToolResultInfo {
  tool_call_id: string;
  name: string;
  content: string;
  is_error: boolean;
}

export interface ChatStreamDelta {
  type: "text" | "reasoning" | "tool_call" | "tool_result" | "error" | "done";
  content?: string | null;
  tool_call?: ToolCallInfo | null;
  tool_result?: ToolResultInfo | null;
  error?: string | null;
  reasoning_content?: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant" | "tool";
  content: string | null;
  tool_calls?: ToolCallInfo[] | null;
  tool_call_id?: string | null;
  name?: string | null;
  reasoning_content?: string | null;
}

export interface ToolCallDisplay {
  id: string;
  name: string;
  arguments: string;
  result?: string;
  isError?: boolean;
  isExecuting?: boolean;
}

export interface ChatDisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCallDisplay[];
  reasoningContent?: string;
  isStreaming?: boolean;
}
