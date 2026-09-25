import { describe, expect, it, vi } from "vitest";
import { createStreamDeltaBatcher } from "./streamDeltaBatcher";

describe("createStreamDeltaBatcher", () => {
  it("merges text and reasoning within one scheduled frame", () => {
    let scheduled: (() => void) | null = null;
    const onFlush = vi.fn();
    const schedule = vi.fn((callback: () => void) => {
      scheduled = callback;
      return 7;
    });
    const batcher = createStreamDeltaBatcher(onFlush, schedule, vi.fn());

    batcher.enqueueText("a");
    batcher.enqueueText("b");
    batcher.enqueueReasoning("r1");

    expect(schedule).toHaveBeenCalledTimes(1);
    expect(onFlush).not.toHaveBeenCalled();
    (scheduled as (() => void) | null)?.();
    expect(onFlush).toHaveBeenCalledWith({ text: "ab", reasoning: "r1" });
  });

  it("flushes immediately and cancels the pending frame", () => {
    const onFlush = vi.fn();
    const cancel = vi.fn();
    const batcher = createStreamDeltaBatcher(onFlush, () => 11, cancel);

    batcher.enqueueReasoning("reasoning");
    batcher.flush();

    expect(cancel).toHaveBeenCalledWith(11);
    expect(onFlush).toHaveBeenCalledWith({ text: "", reasoning: "reasoning" });
  });

  it("clears pending content without emitting it", () => {
    const onFlush = vi.fn();
    const cancel = vi.fn();
    const batcher = createStreamDeltaBatcher(onFlush, () => 3, cancel);

    batcher.enqueueText("discarded");
    batcher.clear();
    batcher.flush();

    expect(cancel).toHaveBeenCalledWith(3);
    expect(onFlush).not.toHaveBeenCalled();
  });
});

it("separates reasoning blocks even within the same animation frame", () => {
  const onFlush = vi.fn();
  const batcher = createStreamDeltaBatcher(onFlush, () => 1, vi.fn());
  const source = { block_id: "a", source: "财务分析", stage: "agent" as const, turn: 1, attempt: 1 };
  batcher.enqueueReasoning("先", source);
  batcher.enqueueReasoning("分析", source);
  batcher.enqueueReasoning("再分析", { ...source, block_id: "b", turn: 2 });
  batcher.flush();
  expect(onFlush.mock.calls.map(([batch]) => [batch.reasoning, batch.reasoningSource.block_id])).toEqual([
    ["先分析", "a"], ["再分析", "b"],
  ]);
});
