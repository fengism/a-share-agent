import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { AnalysisResult } from "../../types/stock";
import AnalysisPanels from "./AnalysisPanels";

vi.mock("../../hooks/useMediaQuery", () => ({
  useMediaQuery: () => false,
}));

vi.mock("./FundamentalPanel", () => ({ default: () => <div>基本面内容</div> }));
vi.mock("./ResearchFrameworkPanel", () => ({ default: () => <div>投资研究内容</div> }));
vi.mock("./TechnicalPanel", () => ({ default: () => <div>技术面内容</div> }));
vi.mock("./ValuationPanel", () => ({ default: () => <div>估值面内容</div> }));
vi.mock("./SentimentPanel", () => ({ default: () => <div>情绪面内容</div> }));
vi.mock("./AIConclusion", () => ({ default: () => <div>综合研判内容</div> }));
vi.mock("./AnalysisDecisionBoard", () => ({ default: () => <div>行动建议内容</div> }));

describe("AnalysisPanels", () => {
  it("hides the research conclusion until a research result exists", async () => {
    const { rerender } = render(
      <MemoryRouter initialEntries={["/analysis/600519"]}>
        <AnalysisPanels
          code="600519"
          result={null}
          isExportingPdf={false}
        />
      </MemoryRouter>,
    );

    expect(screen.queryByRole("tab", { name: "研究结论" })).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "基本面" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("基本面内容")).toBeInTheDocument();

    rerender(
      <MemoryRouter initialEntries={["/analysis/600519"]}>
        <AnalysisPanels
          code="600519"
          result={{} as AnalysisResult}
          isExportingPdf={false}
        />
      </MemoryRouter>,
    );

    expect(await screen.findByText("投资研究内容")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "研究结论" })).toHaveAttribute("aria-selected", "true");
  });

  it("uses investment research as the default panel", async () => {
    render(
      <MemoryRouter initialEntries={["/analysis/600519"]}>
        <AnalysisPanels
          code="600519"
          result={{} as AnalysisResult}
          isExportingPdf={false}
        />
      </MemoryRouter>,
    );

    expect(await screen.findByText("投资研究内容")).toBeInTheDocument();
    expect(screen.getByText("综合研判内容")).toBeInTheDocument();
    expect(screen.getByText("行动建议内容")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "研究结论" })).toHaveAttribute("aria-selected", "true");

    fireEvent.click(screen.getByRole("tab", { name: "基本面" }));
    expect(screen.getByText("基本面内容")).toBeInTheDocument();
    expect(screen.queryByText("综合研判内容")).not.toBeInTheDocument();
    expect(screen.queryByText("投资研究内容")).not.toBeInTheDocument();
  });

  it("includes every panel when exporting a PDF", async () => {
    render(
      <MemoryRouter>
        <AnalysisPanels
          code="600519"
          result={{} as AnalysisResult}
          isExportingPdf
        />
      </MemoryRouter>,
    );

    expect(await screen.findByText("投资研究内容")).toBeInTheDocument();
    expect(screen.getByText("基本面内容")).toBeInTheDocument();
    expect(await screen.findByText("技术面内容")).toBeInTheDocument();
    expect(await screen.findByText("估值面内容")).toBeInTheDocument();
    expect(await screen.findByText("情绪面内容")).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "公告" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "研报评级" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "资金流向" })).not.toBeInTheDocument();
  });
});
