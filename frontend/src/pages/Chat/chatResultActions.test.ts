import { describe, expect, it } from "vitest";
import { extractChatResultContext } from "./chatResultActions";

describe("extractChatResultContext", () => {
  it("extracts stock codes and structured screener filters from tool calls", () => {
    const context = extractChatResultContext({
      id: "assistant-1",
      role: "assistant",
      content: "候选股票包括贵州茅台 600519 与平安银行 000001。",
      toolCalls: [{
        id: "tool-1",
        name: "screen_stocks",
        arguments: JSON.stringify({ pe_max: 15, market_cap_min: 200, concepts: ["低空经济"], sort_by: "pe", sort_order: "asc" }),
        result: JSON.stringify({ items: [{ code: "600519" }, { code: "000001" }] }),
      }],
      isStreaming: false,
    });

    expect(context.stockCodes).toEqual(["600519", "000001"]);
    expect(context.screenerState?.filters).toMatchObject({
      pe_max: 15,
      market_cap_min: 200,
      concepts: ["低空经济"],
      sort_by: "pe",
      sort_order: "asc",
      page: 1,
    });
  });

  it("does not treat unrelated six digit values in tool arguments as stocks", () => {
    const context = extractChatResultContext({
      id: "assistant-1",
      role: "assistant",
      content: "筛选完成。",
      toolCalls: [{
        id: "tool-1",
        name: "screen_stocks",
        arguments: JSON.stringify({ market_cap_max: 200000 }),
      }],
      isStreaming: false,
    });

    expect(context.stockCodes).toEqual([]);
  });
});
