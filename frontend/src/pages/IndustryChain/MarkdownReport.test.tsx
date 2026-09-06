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

  it("preserves long Chinese, unbroken text, and URLs in their own blocks", () => {
    const longChinese = "机器人产业链商业化进程需要结合量产交付能力和真实场景泛化能力持续判断".repeat(5);
    const longEnglish = "UnbrokenResearchConclusionIdentifier".repeat(8);
    const longUrl = `https://example.com/${"continuous-url-segment".repeat(12)}`;

    const { container } = render(
      <MarkdownReport
        content={`## ${longChinese}

${longEnglish}

[${longUrl}](${longUrl})

| 指标 | 数据 |
| --- | --- |
| 长文本 | ${longChinese} |`}
      />,
    );

    expect(screen.getByRole("heading", { name: longChinese })).toBeInTheDocument();
    expect(screen.getByText(longEnglish).tagName).toBe("P");
    expect(screen.getByRole("link", { name: longUrl })).toHaveAttribute("href", longUrl);
    expect(screen.getByRole("table").parentElement).toHaveClass("industry-markdown-table-wrap");
    expect(container.querySelector(".industry-markdown pre")).not.toBeInTheDocument();
  });
});
