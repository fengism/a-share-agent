export interface ToolCallFunction {
  name: string;
  arguments: string;
}

export interface ToolCallInfo {
  id: string;
  type: "function";
  function: ToolCallFunction;
}

export interface ToolResultInfo {
  tool_call_id: string;
  name: string;
  content: string;
  is_error: boolean;
}

export interface AgentToolSource {
  title?: string;
  url: string;
  domain?: string;
}

export interface AgentToolResultSummary {
  summary: string;
  status?: "success" | "error" | "skipped";
  sources?: AgentToolSource[];
  metadata?: Record<string, string>;
}

export type AgentPlanStepStatus =
  | "pending"
  | "running"
  | "completed"
  | "degraded"
  | "failed"
  | "cancelled";

export type AgentExecutionStatus = "completed" | "partial" | "failed";

export interface AgentPlanStep {
  id: string;
  title: string;
  description?: string | null;
  agent_name?: string | null;
  dependencies: string[];
  status: AgentPlanStepStatus;
  detail?: string | null;
  attempt: number;
}

export interface AgentPlan {
  summary?: string | null;
  steps: AgentPlanStep[];
}

export interface AgentPlanStepUpdate {
  step_id: string;
  status: AgentPlanStepStatus;
  detail?: string | null;
  attempt: number;
}

export interface ChatStreamDelta {
  type:
    | "status"
    | "plan"
    | "plan_step"
    | "text"
    | "reasoning"
    | "tool_call"
    | "tool_result"
    | "error"
    | "done";
  content?: string | null;
  plan?: AgentPlan | null;
  plan_step?: AgentPlanStepUpdate | null;
  tool_call?: ToolCallInfo | null;
  tool_result?: ToolResultInfo | null;
  tool_result_summary?: AgentToolResultSummary | null;
  error?: string | null;
  reasoning_content?: string | null;
  status?: AgentExecutionStatus | null;
  warnings?: string[];
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
  resultSummary?: AgentToolResultSummary;
  isError?: boolean;
  isSkipped?: boolean;
  isExecuting?: boolean;
  isCancelled?: boolean;
}

export interface ChatDisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCallDisplay[];
  plan?: AgentPlan;
  reasoningContent?: string;
  status?: string;
  isStreaming?: boolean;
}
