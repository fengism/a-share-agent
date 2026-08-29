import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AnalysisStateSection from "./AnalysisStateSection";

vi.mock("../../components/workflows/AnalysisProgressSteps", () => ({
  default: () => <div>分析进度</div>,
}));

vi.mock("../../components/AgentProcessPanel", () => ({
  default: () => <div>Agent 执行过程</div>,
}));

describe("AnalysisStateSection", () => {
  it("does not render an intermediate AI research conclusion while running", () => {
    render(
      <AnalysisStateSection
        isAnalyzing
        error={null}
        stages={[]}
        currentStageIndex={0}
        agentProcess={{
          status: "",
          toolCalls: [],
        }}
      />,
    );

    expect(screen.getByText("Agent 执行过程")).toBeInTheDocument();
    expect(screen.queryByText("AI 正在研究")).not.toBeInTheDocument();
    expect(screen.queryByText("AI 综合研判")).not.toBeInTheDocument();
  });
});
