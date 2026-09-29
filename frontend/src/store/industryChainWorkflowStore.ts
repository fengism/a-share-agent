import { create } from "zustand";
import type { WorkflowStream } from "../api/sse";
import type { IndustryChainResult, IndustryChainResearchScope } from "../types/stock";
import {
  createAgentProcessState,
  stopAgentProcess,
  type AgentProcessState,
} from "../features/agent-process/agentProcess";
import { registerUserScopeHandler } from "./userScope";

export type IndustryWorkflowStatus = "idle" | "running" | "success" | "warning" | "error" | "cancelled" | "detached";

interface IndustryChainWorkflowState {
  status: IndustryWorkflowStatus;
  runId: number;
  jobId: string;
  name: string;
  scope: IndustryChainResearchScope | null;
  isAnalyzing: boolean;
  isCancelling: boolean;
  currentStage: number;
  failedStage: number;
  stageMessage: string;
  result: IndustryChainResult | null;
  archiveId: string;
  error: string;
  agentProcess: AgentProcessState;
  stream: WorkflowStream<IndustryChainResult> | null;
  begin: (name: string, scope: IndustryChainResearchScope) => number;
  patch: (runId: number, patch: Partial<IndustryChainWorkflowState>) => void;
  setStream: (runId: number, stream: WorkflowStream<IndustryChainResult>) => void;
  stopRun: (runId: number, outcome: "cancelled" | "detached") => void;
  cancelActiveRun: () => Promise<"cancelled" | "detached" | "completed" | null>;
  clear: () => void;
}

const initialState = () => ({
  status: "idle" as IndustryWorkflowStatus,
  runId: 0,
  jobId: "",
  name: "",
  scope: null,
  isAnalyzing: false,
  isCancelling: false,
  currentStage: -1,
  failedStage: -1,
  stageMessage: "",
  result: null,
  archiveId: "",
  error: "",
  agentProcess: createAgentProcessState(),
  stream: null as WorkflowStream<IndustryChainResult> | null,
});

export const useIndustryChainWorkflowStore = create<IndustryChainWorkflowState>((set, get) => ({
  ...initialState(),
  begin: (name, scope) => {
    const runId = get().runId + 1;
    set({
      ...initialState(),
      runId,
      name,
      scope,
      isAnalyzing: true,
      status: "running",
    });
    return runId;
  },
  patch: (runId, patch) => set((state) => state.runId === runId ? patch : state),
  setStream: (runId, stream) => set((state) => state.runId === runId ? { stream } : state),
  stopRun: (runId, outcome) => set((state) => {
    if (state.runId !== runId || !state.isAnalyzing) return state;
    const message = outcome === "cancelled" ? "产业研究已取消" : "已停止等待，后台共享任务仍在运行";
    return {
      status: outcome,
      stageMessage: message,
      isAnalyzing: false,
      isCancelling: false,
      error: "",
      agentProcess: stopAgentProcess(state.agentProcess, outcome, message),
      stream: null,
    };
  }),
  cancelActiveRun: async () => {
    const current = get();
    if (!current.isAnalyzing || !current.stream || current.isCancelling) return null;
    const runId = current.runId;
    set({ isCancelling: true, stageMessage: "正在停止产业研究" });
    try {
      const result = await current.stream.cancel();
      if (result === "completed") {
        // DELETE can observe success before the final SSE result reaches this tab.
        set((latest) => latest.runId === runId && latest.isAnalyzing ? {
          stageMessage: "任务已完成，正在接收分析结果",
        } : latest);
      } else {
        get().stopRun(runId, result);
      }
      return result;
    } catch (error) {
      set((latest) => latest.runId === runId && latest.isAnalyzing ? {
        isCancelling: false,
        stageMessage: `停止产业研究失败，任务继续运行：${error instanceof Error ? error.message : "请重试"}`,
      } : latest);
      throw error;
    }
  },
  clear: () => {
    get().stream?.detach();
    set({ ...initialState(), runId: get().runId + 1 });
  },
}));

registerUserScopeHandler(() => {
  useIndustryChainWorkflowStore.getState().clear();
});
