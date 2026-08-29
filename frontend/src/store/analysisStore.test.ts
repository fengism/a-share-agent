import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AnalysisRunIdentity } from "./analysisStore";
import { useAnalysisStore } from "./analysisStore";
import { setActiveUserScope } from "./userScope";

const identity: AnalysisRunIdentity = {
  ownerId: "owner-1",
  runId: "run-1",
  code: "600519",
};

describe("analysisStore ownership", () => {
  beforeEach(() => {
    setActiveUserScope(null);
    useAnalysisStore.getState().resetAnalysis();
  });

  it("detaches work and clears all analysis state when the user changes", () => {
    setActiveUserScope(1);
    const detach = vi.fn();
    useAnalysisStore.getState().beginRun(identity);
    useAnalysisStore.getState().setRunStream(identity, {
      promise: new Promise(() => undefined),
      started: Promise.resolve({ job: { id: "job" }, attached: false }),
      cancel: vi.fn(),
      detach,
    });
    useAnalysisStore.getState().setRunError(identity, "temporary");

    setActiveUserScope(2);

    const state = useAnalysisStore.getState();
    expect(detach).toHaveBeenCalledOnce();
    expect(state.currentCode).toBe("");
    expect(state.activeRun).toBeNull();
    expect(state.analysisResult).toBeNull();
    expect(state.isAnalyzing).toBe(false);
    expect(state.isCancelling).toBe(false);
    expect(state.currentStageIndex).toBe(0);
    expect(state.analysisError).toBeNull();
    expect(state.activeStream).toBeNull();
    expect(state.analysisStages).toHaveLength(0);
  });

  it("sizes progress from the backend stage count", () => {
    useAnalysisStore.getState().beginRun(identity);
    useAnalysisStore.getState().updateRunStage(
      identity,
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

    useAnalysisStore.getState().updateRunStage(
      identity,
      { stage: 3, name: "AI 综合分析", status: "started" },
      3,
      true,
    );

    state = useAnalysisStore.getState();
    expect(state.analysisStages).toHaveLength(3);
    expect(state.analysisStages[2]?.name).toBe("AI 综合分析");
    expect(state.currentStageIndex).toBe(2);
  });

  it("tracks auditable agent plan and tool events for the active run", () => {
    useAnalysisStore.getState().beginRun(identity);
    useAnalysisStore.getState().applyRunAgentEvent(identity, {
      type: "plan",
      plan: {
        summary: "先核验基本面，再检查风险",
        steps: [{
          id: "fundamental",
          title: "基本面证据",
          dependencies: [],
          status: "pending",
          attempt: 0,
        }],
      },
    });
    useAnalysisStore.getState().applyRunAgentEvent(identity, {
      type: "tool_call",
      tool_call: {
        id: "call-1",
        type: "function",
        function: { name: "analyze_financials", arguments: '{"code":"600519"}' },
      },
    });

    const state = useAnalysisStore.getState();
    expect(state.agentProcess.plan?.summary).toBe("先核验基本面，再检查风险");
    expect(state.agentProcess.toolCalls[0]).toEqual(expect.objectContaining({
      name: "analyze_financials",
      isExecuting: true,
    }));
  });

  it("ignores stale mutations from a previous owner", () => {
    const replacement = { ownerId: "owner-2", runId: "run-2", code: "000001" };
    useAnalysisStore.getState().beginRun(identity);
    useAnalysisStore.getState().beginRun(replacement);

    useAnalysisStore.getState().setRunError(identity, "stale");
    useAnalysisStore.getState().finishRun(identity);

    const state = useAnalysisStore.getState();
    expect(state.activeRun).toEqual(replacement);
    expect(state.analysisError).toBeNull();
    expect(state.isAnalyzing).toBe(true);
  });
});
