import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MarkdownReport from "./MarkdownReport";

describe("IndustryChain MarkdownReport", () => {
  it("renders GFM tables, quotes, and source links", () => {
    render(
      <MarkdownReport
        content={`## 市场规模

> 数据来自公开报告

| 指标 | 数据 |
| --- | --- |
| 市场规模 | 2050 亿美元 |

[查看来源](https://example.com/report)`}
      />,
    );

    expect(screen.getByRole("heading", { name: "市场规模" })).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(table).toBeInTheDocument();
    expect(table.parentElement).toHaveClass("industry-markdown-table-wrap");
    expect(screen.getByText("2050 亿美元")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看来源" })).toHaveAttribute("href", "https://example.com/report");
  });
});
