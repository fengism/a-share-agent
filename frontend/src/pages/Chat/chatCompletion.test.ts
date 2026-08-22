import { describe, expect, it } from "vitest";
import { formatChatCompletionNotice } from "./chatCompletion";

describe("formatChatCompletionNotice", () => {
  it("formats and deduplicates terminal warnings", () => {
    expect(formatChatCompletionNotice({
      status: "partial",
      warnings: ["回答可能不完整", "回答可能不完整", "  数据来源受限  "],
    })).toBe("\n\n[提示] 回答可能不完整\n\n[提示] 数据来源受限");
  });

  it("adds a generic notice for partial completion without warnings", () => {
    expect(formatChatCompletionNotice({ status: "partial", warnings: [] }))
      .toBe("\n\n[提示] 回答仅部分完成，请结合工具和步骤状态谨慎参考");
  });

  it("does not alter a normal completed response", () => {
    expect(formatChatCompletionNotice({ status: "completed", warnings: [] })).toBe("");
  });
});
