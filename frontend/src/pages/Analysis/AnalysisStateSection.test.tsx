import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AnalysisStateSection from "./AnalysisStateSection";

import { createAgentProcessState, stopAgentProcess, type AgentProcessState } from "../../features/agent-process/agentProcess";

const running: AgentProcessState = {
  status: "正在采集证据", activeRoundIndex: 1,
  plan: { summary: "调研计划", steps: [{ id: "research", title: "调研", dependencies: [], attempt: 1, status: "running" }] },
  toolCalls: [],
  rounds: [{
    roundIndex: 1, roundTotal: 3, status: "running", objective: "证据核验", evidenceGaps: [],
    toolNames: ["web_fetch"], toolSelectionReason: "获取正文", evidenceAdded: [], judgmentBasis: [],
    conclusion: "", nextStep: "", statusText: "执行中",
    toolCalls: [
      { id: "done", name: "web_fetch", arguments: "{}", isExecuting: false, resultSummary: { summary: "已取得的证据" } },
      { id: "running", name: "web_fetch", arguments: "{}", isExecuting: true },
    ],
  }],
};

describe("AnalysisStateSection", () => {
  it("does not render an intermediate AI research conclusion while running", () => {
    render(
      <AnalysisStateSection
        isAnalyzing
        error={null}
        stages={[]}
        currentStageIndex={0}
        agentProcess={{
          status: "Agent 执行过程",
          toolCalls: [],
          rounds: [],
        }}
      />,
    );

    expect(screen.getByText("Agent 执行过程")).toBeInTheDocument();
    expect(screen.queryByText("AI 正在研究")).not.toBeInTheDocument();
    expect(screen.queryByText("AI 综合研判")).not.toBeInTheDocument();
  });
  it.each(["cancelled", "detached", "failed"] as const)("settles stage, round and tool loading for %s", (termination) => {
    const props = {
      error: null, currentStageIndex: 0,
      stages: [{ stage: 1, name: "数据采集与证据校验", status: "started" as const }, null, null],
    };
    const { container, rerender } = render(<AnalysisStateSection {...props} isAnalyzing agentProcess={running} />);
    expect(container.querySelector('[aria-label="loading"]')).not.toBeNull();
    expect(container.querySelector(".ant-steps-item-process")).not.toBeNull();
    const stopped = stopAgentProcess(running, termination, "研究已停止");
    rerender(<AnalysisStateSection {...props} isAnalyzing={false} agentProcess={stopped} />);
    const toggle = screen.getByRole("button", { name: /Agent 思考与执行/ });
    const label = termination === "failed" ? "执行失败" : termination === "cancelled" ? "已停止" : "已停止等待";
    expect(within(toggle).getByText(label)).toBeInTheDocument();
    expect(within(toggle).queryByText("已完成")).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(container.querySelector('[aria-label="loading"]')).toBeNull();
    expect(container.querySelector(".ant-spin-spinning")).toBeNull();
    expect(container.querySelector(".ant-steps-item-process")).toBeNull();
    expect(screen.getByText("数据采集与证据校验")).toBeInTheDocument();
    expect(screen.getByText("已取得的证据")).toBeInTheDocument();
    // Previously completed evidence remains successful, not the workflow or running round.
    expect(screen.getAllByText("已完成")).toHaveLength(1);
    const roundHeader = screen.getByLabelText("第 1 轮调研").firstElementChild as HTMLElement;
    expect(within(roundHeader).getByText(termination === "failed" ? "失败" : label)).toBeInTheDocument();
  });

  it("shows stopped rather than completed when cancelled before any progress", () => {
    const process = stopAgentProcess(createAgentProcessState(), "cancelled", "个股研究已取消");
    const { container } = render(<AnalysisStateSection isAnalyzing={false} error={null} stages={[]} currentStageIndex={0} agentProcess={process} />);
    expect(screen.getByText("已停止")).toBeInTheDocument();
    expect(screen.queryByText("已完成")).not.toBeInTheDocument();
    expect(container.querySelector('[aria-label="loading"]')).toBeNull();
  });

});
