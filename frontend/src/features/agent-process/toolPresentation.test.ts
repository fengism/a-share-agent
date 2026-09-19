import { describe, expect, it } from "vitest";
import { toolDisplayName } from "./toolPresentation";

describe("toolDisplayName", () => {
  it("distinguishes fixed financial formulas from isolated Python", () => {
    expect(toolDisplayName("financial_calculator")).toBe("财务固定公式");
    expect(toolDisplayName("python_interpreter")).toBe("隔离 Python 计算");
  });

  it("preserves unknown tool names", () => {
    expect(toolDisplayName("custom_tool")).toBe("custom_tool");
  });
});
