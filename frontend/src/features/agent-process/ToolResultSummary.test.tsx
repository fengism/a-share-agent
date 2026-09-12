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
  it("only makes HTTP(S) sources clickable", () => {
    render(
      <ToolResultSummary
        value={{
          status: "success",
          summary: "来源列表",
          sources: [
            { url: "https://example.com/report", title: "安全来源" },
            { url: "javascript:alert(1)", title: "危险来源" },
          ],
        }}
      />,
    );

    expect(screen.getByRole("link", { name: /安全来源/ })).toHaveAttribute(
      "href",
      "https://example.com/report",
    );
    expect(screen.getByText("危险来源").closest("a")).toBeNull();
  });

});
