import { create } from "zustand";
import type { AnalysisResult } from "../types/stock";
import type { AnalysisStage, WorkflowStream } from "../api/sse";
import {
  applyAgentEvent,
  createAgentProcessState,
  stopAgentProcess,
  type AgentProcessState,
} from "../features/agent-process/agentProcess";
import type { ChatStreamDelta } from "../types/chat";
import { registerUserScopeHandler } from "./userScope";

export interface AnalysisRunIdentity {
  ownerId: string;
  runId: string;
  code: string;
}

export type AnalysisEntryRoute = "analysis" | "investment-research";

interface AnalysisState {
  currentCode: string;
  jobId: string;
  preferredRoute: AnalysisEntryRoute;
  activeRun: AnalysisRunIdentity | null;
  analysisResult: AnalysisResult | null;
  isAnalyzing: boolean;
  isCancelling: boolean;
  analysisStages: Array<AnalysisStage | null>;
  currentStageIndex: number;
  agentProcess: AgentProcessState;
  analysisError: string | null;
  activeStream: WorkflowStream<AnalysisResult> | null;
  claimContext: (code: string, preferredRoute?: AnalysisEntryRoute) => void;
  beginRun: (identity: AnalysisRunIdentity) => void;
  setRunStream: (identity: AnalysisRunIdentity, stream: WorkflowStream<AnalysisResult>) => void;
  setRunJobId: (identity: AnalysisRunIdentity, jobId: string) => void;
  updateRunStage: (
    identity: AnalysisRunIdentity,
    stage: AnalysisStage,
    totalStages: number,
    setCurrent?: boolean,
  ) => void;
  applyRunAgentEvent: (identity: AnalysisRunIdentity, event: ChatStreamDelta) => void;
  setRunResult: (identity: AnalysisRunIdentity, result: AnalysisResult) => void;
  setRunError: (identity: AnalysisRunIdentity, error: string | null) => void;
  setRunCancelling: (identity: AnalysisRunIdentity, cancelling: boolean) => void;
  stopRun: (identity: AnalysisRunIdentity, outcome: "cancelled" | "detached") => void;
  cancelActiveRun: () => Promise<"cancelled" | "detached" | "completed" | null>;
  finishRun: (identity: AnalysisRunIdentity) => void;
  resetAnalysis: () => void;
}

function initialAnalysisState() {
  return {
    currentCode: "",
    jobId: "",
    preferredRoute: "analysis" as AnalysisEntryRoute,
    activeRun: null,
    analysisResult: null,
    isAnalyzing: false,
    isCancelling: false,
    analysisStages: [] as Array<AnalysisStage | null>,
    currentStageIndex: 0,
    agentProcess: createAgentProcessState(),
    analysisError: null,
    activeStream: null as WorkflowStream<AnalysisResult> | null,
  };
}

function ownsRun(active: AnalysisRunIdentity | null, identity: AnalysisRunIdentity) {
  return active?.ownerId === identity.ownerId
    && active.runId === identity.runId
    && active.code === identity.code;
}

export const useAnalysisStore = create<AnalysisState>((set, get) => ({
  ...initialAnalysisState(),
  claimContext: (code, preferredRoute) => set((state) => {
    if (state.activeRun) {
      return preferredRoute ? { preferredRoute } : state;
    }
    if (state.currentCode === code) return preferredRoute ? { preferredRoute } : state;
    return {
      ...initialAnalysisState(),
      currentCode: code,
      preferredRoute: preferredRoute ?? state.preferredRoute,
    };
  }),
  beginRun: (identity) => set({
    currentCode: identity.code,
    jobId: "",
    activeRun: identity,
    analysisResult: null,
    isAnalyzing: true,
    isCancelling: false,
    analysisStages: [],
    currentStageIndex: 0,
    agentProcess: createAgentProcessState(),
    analysisError: null,
    activeStream: null,
  }),
  setRunStream: (identity, stream) => set((state) => (
    ownsRun(state.activeRun, identity) ? { activeStream: stream } : state
  )),
  setRunJobId: (identity, jobId) => set((state) => (
    ownsRun(state.activeRun, identity) ? { jobId } : state
  )),
  updateRunStage: (identity, stage, totalStages, setCurrent = false) => set((state) => {
    if (!ownsRun(state.activeRun, identity)) return state;
    const index = stage.stage - 1;
    const stageCount = Math.max(totalStages, stage.stage, state.analysisStages.length);
    const nextStages = Array.from(
      { length: stageCount },
      (_, stageIndex) => state.analysisStages[stageIndex] ?? null,
    );
    nextStages[index] = stage;
    return {
      analysisStages: nextStages,
      currentStageIndex: setCurrent ? index : state.currentStageIndex,
    };
  }),
  applyRunAgentEvent: (identity, event) => set((state) => (
    ownsRun(state.activeRun, identity)
      ? { agentProcess: applyAgentEvent(state.agentProcess, event) }
      : state
  )),
  setRunResult: (identity, result) => set((state) => (
    ownsRun(state.activeRun, identity) ? { analysisResult: result } : state
  )),
  setRunError: (identity, error) => set((state) => (
    ownsRun(state.activeRun, identity) ? { analysisError: error } : state
  )),
  setRunCancelling: (identity, cancelling) => set((state) => (
    ownsRun(state.activeRun, identity) ? { isCancelling: cancelling } : state
  )),
  stopRun: (identity, outcome) => set((state) => {
    if (!ownsRun(state.activeRun, identity)) return state;
    const message = outcome === "cancelled" ? "个股研究已取消" : "已停止等待，后台共享任务仍在运行";
    return {
      isAnalyzing: false,
      isCancelling: false,
      activeStream: null,
      activeRun: null,
      analysisResult: null,
      analysisError: null,
      agentProcess: stopAgentProcess(state.agentProcess, outcome, message),
    };
  }),
  cancelActiveRun: async () => {
    const state = get();
    if (!state.activeRun || !state.activeStream || state.isCancelling) return null;
    const identity = state.activeRun;
    set({ isCancelling: true, analysisError: null });
    try {
      const result = await state.activeStream.cancel();
      // A completed DELETE can arrive before the final SSE result. Keep listening.
      if (result !== "completed") get().stopRun(identity, result);
      return result;
    } catch (error) {
      set((latest) => ownsRun(latest.activeRun, identity)
        ? { isCancelling: false }
        : latest);
      throw error;
    }
  },
  finishRun: (identity) => set((state) => (
    ownsRun(state.activeRun, identity)
      ? {
        isAnalyzing: false, isCancelling: false, activeStream: null, activeRun: null,
        agentProcess: state.analysisError
          ? stopAgentProcess(state.agentProcess, "failed", state.analysisError)
          : state.agentProcess,
      }
      : state
  )),
  resetAnalysis: () => {
    get().activeStream?.detach();
    set(initialAnalysisState());
  },
}));

registerUserScopeHandler(() => {
  useAnalysisStore.getState().resetAnalysis();
});
