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
export type AgentResearchRoundStatus = "running" | "completed" | "degraded";

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

export interface AgentResearchRound {
  round_index: number;
  round_total: number;
  status: AgentResearchRoundStatus;
  objective: string;
  evidence_gaps: string[];
  tool_names: string[];
  tool_selection_reason: string;
  evidence_added: string[];
  judgment_basis: string[];
  conclusion: string;
  next_step: string;
}

export interface ReasoningSource {
  block_id: string;
  source: string;
  stage: "agent" | "synthesis";
  turn: number;
  task_id?: string | null;
  attempt: number;
}

// Offsets into reasoningContent avoid storing the same large text twice.
export interface ReasoningBlock extends ReasoningSource {
  start: number;
  end: number;
}

export interface ChatStreamDelta {
  phase?: "research" | "verification_repair" | null;
  type:
    | "status"
    | "plan"
    | "plan_step"
    | "round_started"
    | "round_completed"
    | "text"
    | "reasoning"
    | "tool_call"
    | "tool_result"
    | "error"
    | "done";
  content?: string | null;
  plan?: AgentPlan | null;
  plan_step?: AgentPlanStepUpdate | null;
  research_round?: AgentResearchRound | null;
  tool_call?: ToolCallInfo | null;
  tool_result?: ToolResultInfo | null;
  tool_result_summary?: AgentToolResultSummary | null;
  error?: string | null;
  reasoning_content?: string | null;
  reasoning_source?: ReasoningSource | null;
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

// Local terminal states are persisted with the public research metadata, not
// added to the upstream research event contract.
export type ChatResearchRound = Omit<AgentResearchRound, "status"> & {
  status: AgentResearchRoundStatus | "cancelled" | "failed";
};

export type ChatProcessUpdate =
  | { type: "status"; content: string }
  | { type: "round"; round: ChatResearchRound };

export type ChatProcessOutcome = AgentExecutionStatus | "cancelled";

export interface ChatDisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCallDisplay[];
  plan?: AgentPlan;
  reasoningContent?: string;
  reasoningBlocks?: ReasoningBlock[];
  processUpdates?: ChatProcessUpdate[];
  processOutcome?: ChatProcessOutcome;
  status?: string;
  isStreaming?: boolean;
}
