import { create } from "zustand";
import type { WorkflowStream } from "../api/sse";
import type { IndustryChainResult, IndustryChainResearchScope } from "../types/stock";
import {
  createAgentProcessState,
  type AgentProcessState,
} from "../features/agent-process/agentProcess";
import { registerUserScopeHandler } from "./userScope";

interface IndustryChainWorkflowState {
  runId: number;
  jobId: string;
  name: string;
  scope: IndustryChainResearchScope | null;
  isAnalyzing: boolean;
  isCancelling: boolean;
  currentStage: number;
  stageMessage: string;
  result: IndustryChainResult | null;
  archiveId: string;
  error: string;
  agentProcess: AgentProcessState;
  stream: WorkflowStream<IndustryChainResult> | null;
  begin: (name: string, scope: IndustryChainResearchScope) => number;
  patch: (runId: number, patch: Partial<IndustryChainWorkflowState>) => void;
  setStream: (runId: number, stream: WorkflowStream<IndustryChainResult>) => void;
  cancelActiveRun: () => Promise<"cancelled" | "detached" | "completed" | null>;
  clear: () => void;
}

const initialState = () => ({
  runId: 0,
  jobId: "",
  name: "",
  scope: null,
  isAnalyzing: false,
  isCancelling: false,
  currentStage: -1,
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
    });
    return runId;
  },
  patch: (runId, patch) => set((state) => state.runId === runId ? patch : state),
  setStream: (runId, stream) => set((state) => state.runId === runId ? { stream } : state),
  cancelActiveRun: async () => {
    const current = get();
    if (!current.stream || current.isCancelling) return null;
    const runId = current.runId;
    set({ isCancelling: true, stageMessage: "正在停止产业研究" });
    try {
      const result = await current.stream.cancel();
      set((latest) => latest.runId === runId ? {
        isAnalyzing: false,
        isCancelling: false,
        stream: null,
      } : latest);
      return result;
    } catch (error) {
      set((latest) => latest.runId === runId ? {
        isCancelling: false,
        error: error instanceof Error ? error.message : "停止产业研究失败",
      } : latest);
      throw error;
    }
  },
  clear: () => {
    get().stream?.detach();
    set(initialState());
  },
}));

registerUserScopeHandler(() => {
  useIndustryChainWorkflowStore.getState().clear();
});
