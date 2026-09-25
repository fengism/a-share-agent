import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createAgentProcessState, stopAgentProcess, type AgentProcessState } from "../../features/agent-process/agentProcess";
import IndustryWorkflowProgress from "./IndustryWorkflowProgress";

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

describe("IndustryWorkflowProgress", () => {
  it.each(["cancelled", "detached"] as const)("stops stage, round and tool spinners for %s", (status) => {
    const { container, rerender } = render(<IndustryWorkflowProgress currentStage={0} status="running" message="调研中" agentProcess={running} />);
    expect(container.querySelectorAll('[aria-label="loading"]').length).toBeGreaterThan(0);
    const stopped = stopAgentProcess(running, status, status === "cancelled" ? "产业研究已取消" : "已停止等待，后台共享任务仍在运行");
    rerender(<IndustryWorkflowProgress currentStage={0} status={status} message={stopped.status} agentProcess={stopped} />);
    const toggle = screen.getByRole("button", { name: /Agent 思考与执行/ });
    expect(within(toggle).getByText(status === "cancelled" ? "已停止" : "已停止等待")).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(container.querySelector('[aria-label="loading"]')).toBeNull();
    expect(container.querySelector(".ant-spin-spinning")).toBeNull();
    expect(within(toggle).queryByText("已完成")).not.toBeInTheDocument();
    // Only the previously completed tool remains successful, not the round/workflow.
    expect(screen.getAllByText("已完成")).toHaveLength(1);
    expect(screen.getByText("数据采集与证据校验")).toBeInTheDocument();
    expect(screen.getByText("1/2 已停止")).toBeInTheDocument();
    expect(screen.getByText("已取得的证据")).toBeInTheDocument();
    const roundHeader = screen.getByLabelText("第 1 轮调研").firstElementChild as HTMLElement;
    expect(within(roundHeader).getByText(status === "cancelled" ? "已停止" : "已停止等待")).toBeInTheDocument();
  });

  it("does not show success when cancelled before the first progress event", () => {
    const process = stopAgentProcess(createAgentProcessState(), "cancelled", "产业研究已取消");
    const { container } = render(<IndustryWorkflowProgress currentStage={-1} status="cancelled" message={process.status} agentProcess={process} />);
    expect(screen.getByText("产业研究已取消")).toBeInTheDocument();
    expect(screen.getByText("已停止")).toBeInTheDocument();
    expect(screen.queryByText("已完成")).not.toBeInTheDocument();
    expect(container.querySelector('[aria-label="loading"]')).toBeNull();
  });

  it("keeps successfully finished research visible when cancelling during synthesis", () => {
    const process = stopAgentProcess({ ...createAgentProcessState(), status: "Agent 调研完成" }, "cancelled", "产业研究已取消");
    const { container } = render(<IndustryWorkflowProgress currentStage={1} status="cancelled" message={process.status} agentProcess={process} />);
    expect(screen.getByText("数据采集与证据校验")).toBeInTheDocument();
    expect(screen.getByText("AI 生成分析报告")).toBeInTheDocument();
    expect(container.querySelectorAll('[aria-label="check-circle"]')).toHaveLength(1);
    expect(container.querySelector('[aria-label="loading"]')).toBeNull();
    expect(screen.getByText("已停止")).toBeInTheDocument();
  });

  it("shows success only for a completed workflow", () => {
    const { container } = render(<IndustryWorkflowProgress currentStage={2} status="success" message="分析完成" agentProcess={{ ...createAgentProcessState(), status: "Agent 调研完成" }} />);
    expect(screen.getByText("已完成")).toBeInTheDocument();
    expect(screen.getByText("分析完成")).toBeInTheDocument();
    expect(container.querySelector('[aria-label="loading"]')).toBeNull();
  });
});
