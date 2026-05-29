import { create } from "zustand";
import type { AnalysisResult } from "../types/stock";
import type { AnalysisStage } from "../api/sse";

const INITIAL_STAGES: AnalysisStage[] = [
  { stage: 1, name: "数据采集", status: "failed" },
  { stage: 2, name: "技术指标计算", status: "failed" },
  { stage: 3, name: "构造分析请求", status: "failed" },
  { stage: 4, name: "AI模型分析", status: "failed" },
];

interface AnalysisState {
  currentCode: string;
  analysisResult: AnalysisResult | null;
  isAnalyzing: boolean;
  analysisStages: AnalysisStage[];
  currentStageIndex: number;
  analysisError: string | null;
  cancelAnalysis: (() => void) | null;
  setCurrentCode: (code: string) => void;
  setAnalysisResult: (result: AnalysisResult | null) => void;
  setIsAnalyzing: (loading: boolean) => void;
  setAnalysisStages: (stages: AnalysisStage[]) => void;
  updateAnalysisStage: (stage: AnalysisStage, setCurrent?: boolean) => void;
  setCurrentStageIndex: (index: number) => void;
  setAnalysisError: (error: string | null) => void;
  setCancelAnalysis: (cancel: (() => void) | null) => void;
  resetAnalysisProgress: () => void;
}

export const useAnalysisStore = create<AnalysisState>((set) => ({
  currentCode: "",
  analysisResult: null,
  isAnalyzing: false,
  analysisStages: [...INITIAL_STAGES],
  currentStageIndex: 0,
  analysisError: null,
  cancelAnalysis: null,
  setCurrentCode: (code) => set({ currentCode: code }),
  setAnalysisResult: (result) => set({ analysisResult: result }),
  setIsAnalyzing: (loading) => set({ isAnalyzing: loading }),
  setAnalysisStages: (stages) => set({ analysisStages: stages }),
  updateAnalysisStage: (stage, setCurrent = false) => set((state) => {
    const index = stage.stage - 1;
    const nextStages = [...state.analysisStages];
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
    analysisStages: [...INITIAL_STAGES],
    currentStageIndex: 0,
    analysisError: null,
  }),
}));
