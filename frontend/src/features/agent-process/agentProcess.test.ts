import { describe, expect, it } from "vitest";
import { stopAgentProcess, type AgentProcessState } from "./agentProcess";

function researchState(): AgentProcessState {
  const tools = [
    { id: "done", name: "web_fetch", arguments: "{}", isExecuting: false, resultSummary: { summary: "已验证的证据" } },
    { id: "running", name: "web_fetch", arguments: "{}", isExecuting: true },
  ];
  const round = {
    roundIndex: 1, roundTotal: 3, status: "completed" as const, objective: "证据核验", evidenceGaps: [],
    toolNames: ["web_fetch"], toolSelectionReason: "获取正文", evidenceAdded: ["已验证的证据"],
    judgmentBasis: [], conclusion: "已确认事实", nextStep: "继续核验", statusText: "完成", toolCalls: [tools[0]],
  };
  return {
    status: "执行中", activeRoundIndex: 2,
    plan: { summary: "计划", steps: ["completed", "running", "pending"].map((status, i) => ({
      id: String(i), title: `步骤${i}`, dependencies: [], attempt: 1,
      status: status as "completed" | "running" | "pending",
    })) },
    toolCalls: tools,
    rounds: [round, { ...round, roundIndex: 2, status: "running", toolCalls: tools }],
  };
}

describe("stopAgentProcess", () => {
  it.each(["cancelled", "detached", "failed"] as const)("settles all unfinished work for %s while preserving evidence", (termination) => {
    const running = researchState();
    const stopped = stopAgentProcess(running, termination, "停止原因");
    expect(stopped).toMatchObject({ termination, status: "停止原因", activeRoundIndex: undefined });
    expect(stopped.plan?.steps.map((step) => step.status)).toEqual([
      "completed", termination === "failed" ? "failed" : "cancelled", termination === "failed" ? "failed" : "cancelled",
    ]);
    expect(stopped.plan?.steps[0]).toBe(running.plan?.steps[0]);
    expect(stopped.toolCalls[0]).toBe(running.toolCalls[0]);
    expect(stopped.toolCalls[1]).toMatchObject({ isExecuting: false, isCancelled: termination !== "failed", isError: termination === "failed" });
    expect(stopped.rounds[0]).toEqual(running.rounds[0]);
    expect(stopped.rounds[1]).toMatchObject({ status: termination, statusText: "停止原因", evidenceAdded: ["已验证的证据"] });
    expect(stopped.rounds[1].toolCalls).toEqual(stopped.toolCalls);
    expect(running.toolCalls[1].isExecuting).toBe(true);
    expect(running.rounds[1].status).toBe("running");
    expect(running.plan?.steps[1].status).toBe("running");
  });
});
