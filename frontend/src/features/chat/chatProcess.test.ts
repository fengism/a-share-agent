import { describe, expect, it } from "vitest";
import type { AgentResearchRound, ChatDisplayMessage } from "../../types/chat";
import { appendProcessUpdate, finalizeChatProcess, restoreChatProcess, MAX_PROCESS_UPDATES, sanitizeProcessUpdates } from "./chatProcess";
import { sanitizeDisplayMessages } from "../../store/chatMessageGuards";

export const researchRound: AgentResearchRound = {
  round_index: 1, round_total: 2, status: "running",
  objective: "核对公司公告", evidence_gaps: ["缺少最新公告"], tool_names: ["web_search"],
  tool_selection_reason: "优先查找一手资料", evidence_added: [], judgment_basis: [], conclusion: "", next_step: "抓取正文",
};

describe("chat process metadata", () => {
  it("deduplicates only adjacent status records and preserves later repeated stages", () => {
    let updates = appendProcessUpdate([], { type: "status", content: " 查找资料 " });
    expect(appendProcessUpdate(updates, { type: "status", content: "查找资料" })).toBe(updates);
    updates = appendProcessUpdate(updates, { type: "status", content: "核对结果" });
    expect(appendProcessUpdate(updates, { type: "status", content: "查找资料" })).toHaveLength(3);
    expect(appendProcessUpdate(updates, { type: "status", content: " " })).toBe(updates);
  });

  it("updates a research round in place without dropping progress records", () => {
    let updates = appendProcessUpdate([], { type: "round", round: researchRound });
    updates = appendProcessUpdate(updates, { type: "status", content: "读取公告" });
    updates = appendProcessUpdate(updates, { type: "round", round: { ...researchRound, status: "completed", evidence_added: ["最新公告"], conclusion: "已核验" } });
    expect(updates).toHaveLength(2);
    expect(updates[0]).toMatchObject({ type: "round", round: { status: "completed", conclusion: "已核验" } });
    expect(updates[1]).toEqual({ type: "status", content: "读取公告" });
  });

  it("bounds records, text, and lists and ignores raw/private or malformed metadata", () => {
    const updates = sanitizeProcessUpdates(Array.from({ length: 100 }, (_, i) => ({ type: "status", content: `stage ${i}` })))!;
    expect(updates).toHaveLength(MAX_PROCESS_UPDATES);
    expect(updates[updates.length - 1]).toEqual({ type: "status", content: "stage 99" });
    expect(sanitizeProcessUpdates([
      { type: "reasoning", content: "private" },
      { type: "text", content: "answer" },
      { type: "round", round: { ...researchRound, judgment_basis: [null] } },
      { type: "round", round: { ...researchRound, round_index: -1 } },
      null,
    ])).toEqual([]);
    const bounded = appendProcessUpdate([], { type: "round", round: { ...researchRound, objective: "x".repeat(8000), evidence_added: Array(20).fill("entry"), reasoning_content: "private" } })[0];
    expect(bounded.type === "round" && bounded.round.objective.length).toBe(2000);
    expect(bounded.type === "round" && bounded.round.evidence_added.length).toBe(12);
    expect(bounded.type === "round" && bounded.round).not.toHaveProperty("reasoning_content");
  });

  it("restores valid records but preserves the answer if snapshot process fields are corrupt", () => {
    const message = { id: "m", role: "assistant", content: "最终结论", processUpdates: [{ type: "round", round: researchRound }], processOutcome: "partial" };
    expect(sanitizeDisplayMessages([message])[0]).toMatchObject(message);
    expect(sanitizeDisplayMessages([{ ...message, processUpdates: [{ type: "round", round: {} }], processOutcome: "oops" }])[0]).toMatchObject({ content: "最终结论", processUpdates: [], processOutcome: undefined });
  });
});

describe("chat process termination", () => {
  const live: ChatDisplayMessage = {
    id: "active", role: "assistant", content: "已有答案", reasoningContent: "已有推理", isStreaming: true,
    status: "抓取正文",
    plan: { steps: [
      { id: "done", title: "检索", dependencies: [], status: "completed", attempt: 1 },
      { id: "live", title: "核验", dependencies: [], status: "running", attempt: 1 },
      { id: "pending", title: "汇总", dependencies: [], status: "pending", attempt: 0 },
    ] },
    toolCalls: [
      { id: "done", name: "web_search", arguments: "{}", isExecuting: false, result: "公告证据" },
      { id: "live", name: "web_fetch", arguments: "{}", isExecuting: true },
    ],
    processUpdates: [
      { type: "round", round: { ...researchRound, status: "completed", evidence_added: ["公告证据"] } },
      { type: "round", round: { ...researchRound, round_index: 2, evidence_added: ["待核验原文"] } },
    ],
  };

  it.each(["cancelled", "failed"] as const)("settles all unfinished work on %s without losing evidence", (outcome) => {
    const settled = finalizeChatProcess(live, outcome);
    expect(settled).toMatchObject({ content: "已有答案", reasoningContent: "已有推理", isStreaming: false, processOutcome: outcome });
    expect(settled.status).toBeUndefined();
    expect(settled.plan?.steps.map((step) => step.status)).toEqual(["completed", outcome, outcome]);
    expect(settled.toolCalls?.[0]).toBe(live.toolCalls?.[0]);
    expect(settled.toolCalls?.[1]).toMatchObject({ isExecuting: false, isCancelled: outcome === "cancelled", isError: outcome === "failed" });
    expect(settled.processUpdates?.[0]).toBe(live.processUpdates?.[0]);
    expect(settled.processUpdates?.[1]).toMatchObject({ round: { status: outcome, evidence_added: ["待核验原文"] } });
    expect(sanitizeDisplayMessages([settled])[0]).toEqual(settled);
    expect(live.isStreaming).toBe(true);
    expect(live.toolCalls?.[1].isExecuting).toBe(true);
    expect(live.processUpdates?.[1]).toMatchObject({ round: { status: "running" } });
  });

  it("restores interrupted snapshots as stopped, including legacy non-streaming tool states", () => {
    for (const isStreaming of [true, false, undefined]) {
      const restored = restoreChatProcess({ ...live, isStreaming });
      expect(restored.processOutcome).toBe("cancelled");
      expect(restored.toolCalls?.every((tool) => !tool.isExecuting)).toBe(true);
      expect(restored.processUpdates?.[1]).toMatchObject({ round: { status: "cancelled" } });
      expect(restoreChatProcess(restored)).toBe(restored);
    }
  });

  it("keeps explicit failure and partial outcomes when restoring unfinished work", () => {
    for (const processOutcome of ["failed", "partial"] as const) {
      expect(restoreChatProcess({ ...live, processOutcome }).processOutcome).toBe(processOutcome);
    }
    const completed = finalizeChatProcess(live, "completed");
    expect(restoreChatProcess(completed)).toBe(completed);
  });
});
