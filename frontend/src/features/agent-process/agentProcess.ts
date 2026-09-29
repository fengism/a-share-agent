import type {
  AgentPlan,
  AgentResearchRound,
  AgentResearchRoundStatus,
  ChatStreamDelta,
  ToolCallDisplay,
} from "../../types/chat";

export type AgentProcessTermination = "cancelled" | "detached" | "failed";

export interface AgentProcessRound {
  phase?: "research" | "verification_repair";
  roundIndex: number;
  roundTotal: number;
  status: AgentResearchRoundStatus | AgentProcessTermination;
  objective: string;
  evidenceGaps: string[];
  toolNames: string[];
  toolSelectionReason: string;
  evidenceAdded: string[];
  judgmentBasis: string[];
  conclusion: string;
  nextStep: string;
  statusText: string;
  toolCalls: ToolCallDisplay[];
}

export interface AgentProcessState {
  plan?: AgentPlan;
  status: string;
  toolCalls: ToolCallDisplay[];
  rounds: AgentProcessRound[];
  activeRoundIndex?: number;
  activeRoundPhase?: "research" | "verification_repair";
  termination?: AgentProcessTermination;
}

export function createAgentProcessState(): AgentProcessState {
  return { status: "", toolCalls: [], rounds: [] };
}

export function hasAgentProcess(state: AgentProcessState): boolean {
  return Boolean(
    state.plan
    || state.status
    || state.toolCalls.length > 0
    || state.rounds.length > 0,
  );
}

export function agentProcessFromEvents(
  events: ChatStreamDelta[] | null | undefined,
): AgentProcessState {
  return (events ?? []).reduce(applyAgentEvent, createAgentProcessState());
}

function toProcessRound(
  value: AgentResearchRound,
  previous?: AgentProcessRound,
): AgentProcessRound {
  return {
    roundIndex: value.round_index,
    roundTotal: value.round_total,
    status: value.status,
    objective: value.objective,
    evidenceGaps: value.evidence_gaps,
    toolNames: value.tool_names,
    toolSelectionReason: value.tool_selection_reason,
    evidenceAdded: value.evidence_added,
    judgmentBasis: value.judgment_basis,
    conclusion: value.conclusion,
    nextStep: value.next_step,
    statusText: previous?.statusText ?? "",
    toolCalls: previous?.toolCalls ?? [],
  };
}

function upsertRound(
  rounds: AgentProcessRound[],
  value: AgentResearchRound,
  phase?: "research" | "verification_repair",
): AgentProcessRound[] {
  const matches = (round: AgentProcessRound) => round.roundIndex === value.round_index && (round.phase ?? "research") === (phase ?? "research");
  const previous = rounds.find(matches);
  const next = { ...toProcessRound(value, previous), phase };
  return [
    ...rounds.filter((round) => !matches(round)),
    next,
  ].sort((left, right) => (left.phase ?? "research").localeCompare(right.phase ?? "research") || left.roundIndex - right.roundIndex);
}

function updateRound(
  rounds: AgentProcessRound[],
  roundIndex: number | undefined,
  update: (round: AgentProcessRound) => AgentProcessRound,
  phase?: "research" | "verification_repair",
): AgentProcessRound[] {
  if (roundIndex === undefined) return rounds;
  return rounds.map((round) => (
    round.roundIndex === roundIndex && (round.phase ?? "research") === (phase ?? "research") ? update(round) : round
  ));
}

function appendToolCall(
  tools: ToolCallDisplay[],
  toolCall: ToolCallDisplay,
): ToolCallDisplay[] {
  return [
    ...tools.filter((item) => item.id !== toolCall.id),
    toolCall,
  ];
}

function applyToolResult(
  tools: ToolCallDisplay[],
  event: ChatStreamDelta,
): ToolCallDisplay[] {
  if (!event.tool_result) return tools;
  const toolResult = event.tool_result;
  return tools.map((item) => (
    item.id === toolResult.tool_call_id
      ? {
          ...item,
          isError: toolResult.is_error && event.tool_result_summary?.status !== "skipped",
          isSkipped: event.tool_result_summary?.status === "skipped",
          isExecuting: false,
          resultSummary: event.tool_result_summary || undefined,
        }
      : item
  ));
}

export function applyAgentEvent(
  state: AgentProcessState,
  event: ChatStreamDelta,
): AgentProcessState {
  if (
    (event.type === "round_started" || event.type === "round_completed")
    && event.research_round
  ) {
    const isStarted = event.type === "round_started";
    return {
      ...state,
      rounds: upsertRound(state.rounds, event.research_round, event.phase ?? undefined),
      activeRoundPhase: isStarted ? event.phase ?? undefined : undefined,
      activeRoundIndex: isStarted ? event.research_round.round_index : undefined,
    };
  }
  if (event.type === "plan" && event.plan) {
    if (!event.phase) return { ...state, plan: event.plan };
    const phasePrefix = `${event.phase}:`;
    return { ...state, plan: {
      summary: event.plan.summary,
      steps: [...(state.plan?.steps ?? []).filter((step) => !step.id.startsWith(phasePrefix)), ...event.plan.steps],
    } };
  }
  if (event.type === "plan_step" && event.plan_step && state.plan) {
    const update = event.plan_step;
    return {
      ...state,
      plan: {
        ...state.plan,
        steps: state.plan.steps.map((step) => (
          step.id === update.step_id
            ? { ...step, status: update.status, detail: update.detail, attempt: update.attempt }
            : step
        )),
      },
    };
  }
  if (event.type === "status") {
    const status = event.content || "Agent 正在执行";
    return {
      ...state,
      status,
      rounds: updateRound(state.rounds, state.activeRoundIndex, (round) => ({
        ...round,
        statusText: status,
      }), state.activeRoundPhase),
    };
  }
  if (event.type === "tool_call" && event.tool_call) {
    const toolCall: ToolCallDisplay = {
      id: event.tool_call.id,
      name: event.tool_call.function.name,
      arguments: event.tool_call.function.arguments,
      isExecuting: true,
    };
    return {
      ...state,
      toolCalls: appendToolCall(state.toolCalls, toolCall),
      rounds: updateRound(state.rounds, state.activeRoundIndex, (round) => ({
        ...round,
        toolCalls: appendToolCall(round.toolCalls, toolCall),
      }), state.activeRoundPhase),
    };
  }
  if (event.type === "tool_result" && event.tool_result) {
    return {
      ...state,
      toolCalls: applyToolResult(state.toolCalls, event),
      rounds: updateRound(state.rounds, state.activeRoundIndex, (round) => ({
        ...round,
        toolCalls: applyToolResult(round.toolCalls, event),
      }), state.activeRoundPhase),
    };
  }
  if (event.type === "error") {
    return { ...state, status: event.error || "Agent 执行失败", activeRoundIndex: undefined, activeRoundPhase: undefined };
  }
  if (event.type === "done") {
    return { ...state, status: "Agent 调研完成", activeRoundIndex: undefined, activeRoundPhase: undefined };
  }
  return state;
}

/** Stop local progress without turning unfinished work into successful evidence. */
export function stopAgentProcess(
  state: AgentProcessState,
  termination: AgentProcessTermination,
  message: string,
): AgentProcessState {
  const stopTools = (tools: ToolCallDisplay[]) => tools.map((tool) => tool.isExecuting ? {
    ...tool,
    isExecuting: false,
    isCancelled: termination !== "failed",
    isError: termination === "failed",
  } : tool);
  return {
    ...state,
    termination,
    status: message,
    activeRoundIndex: undefined, activeRoundPhase: undefined,
    plan: state.plan ? {
      ...state.plan,
      steps: state.plan.steps.map((step) => step.status === "running" || step.status === "pending" ? {
        ...step,
        status: termination === "failed" ? "failed" : "cancelled",
        detail: message,
      } : step),
    } : undefined,
    toolCalls: stopTools(state.toolCalls),
    rounds: state.rounds.map((round) => ({
      ...round,
      ...(round.status === "running" ? { status: termination, statusText: message } : {}),
      toolCalls: stopTools(round.toolCalls),
    })),
  };
}
