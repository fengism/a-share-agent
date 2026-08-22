import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAnalysisStore } from "./analysisStore";
import { setActiveUserScope } from "./userScope";

describe("analysisStore user scope", () => {
  beforeEach(() => {
    setActiveUserScope(null);
    useAnalysisStore.getState().resetAnalysis();
  });

  it("cancels work and clears all analysis state when the user changes", () => {
    setActiveUserScope(1);
    const cancel = vi.fn();
    useAnalysisStore.setState({
      currentCode: "600519",
      analysisResult: { stock_code: "600519" } as never,
      isAnalyzing: true,
      analysisStages: [{ stage: 1, name: "数据采集", status: "completed" }],
      currentStageIndex: 2,
      analysisError: "temporary",
      cancelAnalysis: cancel,
    });

    setActiveUserScope(2);

    const state = useAnalysisStore.getState();
    expect(cancel).toHaveBeenCalledOnce();
    expect(state.currentCode).toBe("");
    expect(state.analysisResult).toBeNull();
    expect(state.isAnalyzing).toBe(false);
    expect(state.currentStageIndex).toBe(0);
    expect(state.analysisError).toBeNull();
    expect(state.cancelAnalysis).toBeNull();
    expect(state.analysisStages).toHaveLength(0);
  });

  it("sizes progress from the backend stage count", () => {
    useAnalysisStore.getState().updateAnalysisStage(
      { stage: 1, name: "Agent 调研与证据校验", status: "started" },
      3,
      true,
    );

    let state = useAnalysisStore.getState();
    expect(state.analysisStages).toHaveLength(3);
    expect(state.analysisStages[0]?.name).toBe("Agent 调研与证据校验");
    expect(state.analysisStages[1]).toBeNull();
    expect(state.analysisStages[2]).toBeNull();
    expect(state.currentStageIndex).toBe(0);

    useAnalysisStore.getState().updateAnalysisStage(
      { stage: 3, name: "AI 综合分析", status: "started" },
      3,
      true,
    );

    state = useAnalysisStore.getState();
    expect(state.analysisStages).toHaveLength(3);
    expect(state.analysisStages[2]?.name).toBe("AI 综合分析");
    expect(state.currentStageIndex).toBe(2);
  });
});
