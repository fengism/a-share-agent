import { describe, expect, it, vi } from "vitest";
import { runBatchAnalysis } from "./batchAnalysis";

describe("runBatchAnalysis", () => {
  it("limits concurrency and reports individual failures", async () => {
    let active = 0;
    let maxActive = 0;
    const progress = vi.fn();
    const start = vi.fn(async (code: string) => {
      active += 1;
      maxActive = Math.max(maxActive, active);
      await Promise.resolve();
      active -= 1;
      if (code === "000002") throw new Error("failed");
    });

    const result = await runBatchAnalysis(
      ["600519", "000001", "000002", "000003"],
      start,
      progress,
      2,
    );

    expect(maxActive).toBe(2);
    expect(result.succeeded).toEqual(["600519", "000001", "000003"]);
    expect(result.failed).toEqual(["000002"]);
    expect(progress).toHaveBeenLastCalledWith(4, 4);
  });
});
