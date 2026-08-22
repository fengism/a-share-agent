import { describe, expect, it } from "vitest";
import type { ChatCapabilitiesResponse } from "../../types/capabilities";
import { filterCapabilities, formatCacheTtl } from "./capabilityHelpers";

const capabilities: ChatCapabilitiesResponse = {
  skills: [{
    name: "stock_analysis",
    description: "个股分析",
    triggers: ["股票代码"],
    tool_names: ["analyze_stock"],
    rules: ["全面分析"],
    exclusions: [],
    priority: 30,
  }],
  agents: [],
  tools: [{
    name: "analyze_stock",
    description: "个股全维度分析",
    parameters: { type: "object", properties: { code: { type: "string" } } },
    policy: {
      cost: "high",
      cache_ttl_seconds: 60,
      freshness: "near_realtime",
      scope: "public",
      timeout_seconds: 180,
      max_parallel_calls: 2,
      max_result_characters: 12_000,
    },
    skill_names: ["stock_analysis"],
  }],
  unassigned_tools: [],
};

describe("capability helpers", () => {
  it("filters skills and tools by names and parameter fields", () => {
    expect(filterCapabilities(capabilities, "股票").skills).toHaveLength(1);
    expect(filterCapabilities(capabilities, "code").tools).toHaveLength(1);
    expect(filterCapabilities(capabilities, "macro").tools).toHaveLength(0);
  });

  it("formats cache ttl for display", () => {
    expect(formatCacheTtl(0)).toBe("不缓存");
    expect(formatCacheTtl(30)).toBe("30 秒");
    expect(formatCacheTtl(300)).toBe("5 分钟");
    expect(formatCacheTtl(3600)).toBe("1 小时");
  });
});
