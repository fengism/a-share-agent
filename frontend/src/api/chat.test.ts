import { describe, expect, it } from "vitest";
import type { ChatMessage } from "../types/chat";
import { buildChatRequestPayload, prepareChatHistory } from "./chat";

describe("prepareChatHistory", () => {
  it("keeps completed user and assistant text while dropping tool protocol", () => {
    const history: ChatMessage[] = [
      { role: "user", content: "分析茅台" },
      {
        role: "assistant",
        content: null,
        tool_calls: [{
          id: "call-1",
          type: "function",
          function: { name: "get_stock_info", arguments: "{}" },
        }],
      },
      { role: "tool", content: "large payload", tool_call_id: "call-1" },
      { role: "assistant", content: "最终结论", reasoning_content: "internal" },
    ];

    expect(prepareChatHistory(history, "继续")).toEqual([
      { role: "user", content: "分析茅台" },
      { role: "assistant", content: "最终结论" },
    ]);
  });

  it("drops a duplicated current user message", () => {
    expect(prepareChatHistory(
      [{ role: "user", content: "继续分析" }],
      "继续分析",
    )).toBeUndefined();
  });

  it("includes session-level capability overrides only when explicitly selected", () => {
    expect(buildChatRequestPayload("分析风险", undefined, {
      agentNames: ["risk"],
      skillNames: ["market_data"],
    })).toEqual({
      message: "分析风险",
      history: undefined,
      agent_names: ["risk"],
      skill_names: ["market_data"],
    });
    expect(buildChatRequestPayload("自动分析", undefined)).toEqual({
      message: "自动分析",
      history: undefined,
    });
  });
});
