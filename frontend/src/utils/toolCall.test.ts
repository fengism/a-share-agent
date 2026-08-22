import { describe, expect, it } from "vitest";
import { formatToolArguments } from "./toolCall";

describe("formatToolArguments", () => {
  it("formats JSON arguments and normalizes empty arguments", () => {
    expect(formatToolArguments('{"query":"AI服务器"}')).toBe('{\n  "query": "AI服务器"\n}');
    expect(formatToolArguments(" ")).toBe("{}");
  });

  it("keeps non-JSON arguments unchanged", () => {
    expect(formatToolArguments("query=AI服务器")).toBe("query=AI服务器");
  });
});
