import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CitationText, { renderWithCitations } from "./CitationText";

describe("CitationText", () => {
  it("renders plain text without citations as string", () => {
    const text = "公司盈利能力稳固，护城河极深。";
    expect(renderWithCitations(text)).toBe(text);
  });

  it("replaces known citations with interactive tag badges", () => {
    const text = "三季报显示营收同比增长25.3% [^analyze_financials]，董秘在平台确认大单签署 [^get_interactive_qa]。";
    render(<CitationText text={text} />);

    expect(screen.getByText("官方财报")).toBeInTheDocument();
    expect(screen.getByText("董秘互动问答")).toBeInTheDocument();
    expect(screen.getByText(/三季报显示营收同比增长25.3%/)).toBeInTheDocument();
  });

  it("handles unknown citations gracefully", () => {
    const text = "据行业协会披露 [^industry_custom_source] 销量第一。";
    render(<CitationText text={text} />);

    expect(screen.getByText("industry custom source")).toBeInTheDocument();
  });
});
