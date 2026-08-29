import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ToolResultSummary from "./ToolResultSummary";

describe("ToolResultSummary", () => {
  it("uses one typography scale for its label and content", () => {
    render(
      <ToolResultSummary
        value={{
          status: "success",
          summary: "返回 3 条记录",
          metadata: { source: "bing_cn" },
        }}
      />,
    );

    const summary = screen.getByTestId("tool-result-summary");
    expect(summary).toHaveStyle({
      fontSize: "var(--c-font-sm)",
      lineHeight: "var(--c-leading-relaxed)",
    });
    expect(screen.getByText("结果摘要")).toHaveStyle({ fontSize: "inherit" });
    expect(screen.getByText("返回 3 条记录")).toHaveStyle({ fontSize: "inherit" });
  });
});
