import { create } from "zustand";
import type { AnalysisResult } from "../types/stock";
import type { AnalysisStage } from "../api/sse";
import { registerUserScopeHandler } from "./userScope";

interface AnalysisState {
  currentCode: string;
  analysisResult: AnalysisResult | null;
  isAnalyzing: boolean;
  analysisStages: Array<AnalysisStage | null>;
  currentStageIndex: number;
  analysisError: string | null;
  cancelAnalysis: (() => void) | null;
  setCurrentCode: (code: string) => void;
  setAnalysisResult: (result: AnalysisResult | null) => void;
  setIsAnalyzing: (loading: boolean) => void;
  setAnalysisStages: (stages: Array<AnalysisStage | null>) => void;
  updateAnalysisStage: (stage: AnalysisStage, totalStages: number, setCurrent?: boolean) => void;
  setCurrentStageIndex: (index: number) => void;
  setAnalysisError: (error: string | null) => void;
  setCancelAnalysis: (cancel: (() => void) | null) => void;
  resetAnalysisProgress: () => void;
  resetAnalysis: () => void;
}

function initialAnalysisState() {
  return {
    currentCode: "",
    analysisResult: null,
    isAnalyzing: false,
    analysisStages: [] as Array<AnalysisStage | null>,
    currentStageIndex: 0,
    analysisError: null,
    cancelAnalysis: null,
  };
}

export const useAnalysisStore = create<AnalysisState>((set, get) => ({
  ...initialAnalysisState(),
  setCurrentCode: (code) => set({ currentCode: code }),
  setAnalysisResult: (result) => set({ analysisResult: result }),
  setIsAnalyzing: (loading) => set({ isAnalyzing: loading }),
  setAnalysisStages: (stages) => set({ analysisStages: stages }),
  updateAnalysisStage: (stage, totalStages, setCurrent = false) => set((state) => {
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
  setCurrentStageIndex: (index) => set({ currentStageIndex: index }),
  setAnalysisError: (error) => set({ analysisError: error }),
  setCancelAnalysis: (cancel) => set({ cancelAnalysis: cancel }),
  resetAnalysisProgress: () => set({
    analysisStages: [],
    currentStageIndex: 0,
    analysisError: null,
  }),
  resetAnalysis: () => {
    get().cancelAnalysis?.();
    set(initialAnalysisState());
  },
}));

registerUserScopeHandler(() => {
  useAnalysisStore.getState().resetAnalysis();
});
