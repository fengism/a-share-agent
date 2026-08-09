import type { AgentPlan, ChatStreamDelta, ToolCallDisplay } from "../../types/chat";

export interface IndustryAgentProcessState {
  plan?: AgentPlan;
  status: string;
  toolCalls: ToolCallDisplay[];
}

export function createIndustryAgentProcessState(): IndustryAgentProcessState {
  return { status: "", toolCalls: [] };
}

export function applyIndustryAgentEvent(
  state: IndustryAgentProcessState,
  event: ChatStreamDelta,
): IndustryAgentProcessState {
  if (event.type === "plan" && event.plan) {
    return { ...state, plan: event.plan };
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
    return { ...state, status: event.content || "Agent 正在执行" };
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
      toolCalls: [
        ...state.toolCalls.filter((item) => item.id !== toolCall.id),
        toolCall,
      ],
    };
  }
  if (event.type === "tool_result" && event.tool_result) {
    const toolResult = event.tool_result;
    return {
      ...state,
      toolCalls: state.toolCalls.map((item) => (
        item.id === toolResult.tool_call_id
          ? {
              ...item,
              result: toolResult.content,
              isError: toolResult.is_error,
              isExecuting: false,
            }
          : item
      )),
    };
  }
  if (event.type === "error") {
    return { ...state, status: event.error || "Agent 执行失败" };
  }
  if (event.type === "done") {
    return { ...state, status: "Agent 调研完成" };
  }
  return state;
}
