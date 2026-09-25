import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { AnalysisResult } from "../../types/stock";
import AnalysisPanels from "./AnalysisPanels";
import AnalysisResultSection from "./AnalysisResultSection";

vi.mock("./FundamentalPanel", () => ({ default: () => <div>基本面内容</div> }));
vi.mock("./analysisPanelLoaders", () => ({
  loadResearchFrameworkPanel: async () => ({
    default: ({ forceFullReport, onOpenValuation }: { forceFullReport: boolean; onOpenValuation?: () => void }) => (
      <div>
        <div>{forceFullReport ? "完整投资研究内容" : "投资研究内容"}</div>
        {!forceFullReport && <button onClick={onOpenValuation}>查看估值明细</button>}
      </div>
    ),
  }),
  loadValuationPanel: async () => ({ default: () => <div>估值面内容</div> }),
}));
vi.mock("./AIConclusion", () => ({ default: () => <div>综合研判内容</div> }));
vi.mock("./AnalysisDecisionBoard", () => ({ default: () => <div>行动建议内容</div> }));

function AnalysisSections({ result, isExportingPdf = false }: {
  result: AnalysisResult | null;
  isExportingPdf?: boolean;
}) {
  return (
    <>
      <AnalysisPanels code="600519" result={result} isExportingPdf={isExportingPdf} />
      <AnalysisResultSection result={result} isExportingPdf={isExportingPdf} />
    </>
  );
}

describe("AnalysisPanels and the independent result section", () => {
  it("does not render a dimension container before or after analysis completes", async () => {
    const { rerender, container } = render(
      <MemoryRouter><AnalysisSections result={null} /></MemoryRouter>,
    );
    expect(container).toBeEmptyDOMElement();
    rerender(<MemoryRouter><AnalysisSections result={{} as AnalysisResult} /></MemoryRouter>);
    expect(await screen.findByText("投资研究内容")).toBeVisible();
    expect(screen.getByText("综合研判内容")).toBeVisible();
    expect(screen.getByText("行动建议内容")).toBeVisible();
    expect(screen.getAllByRole("tab")).toHaveLength(1);
    expect(screen.getByRole("tab", { name: "研究结论" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByRole("tab", { name: "技术面" })).not.toBeInTheDocument();
    expect(container.querySelector(".analysis-panels-card, #analysis-details")).toBeNull();
    expect(screen.getByRole("region", { name: "个股分析结果" }).previousElementSibling).toBeNull();
  });

  it.each(["technical", "research", "fundamental", "sentiment"])(
    "keeps results accessible for legacy panel=%s URLs without reviving dimensions", async (panel) => {
      render(
        <MemoryRouter initialEntries={[`/analysis/600519?panel=${panel}`]}>
          <AnalysisSections result={{} as AnalysisResult} />
        </MemoryRouter>,
      );
      expect(await screen.findByText("投资研究内容")).toBeVisible();
      expect(screen.getAllByRole("tab")).toHaveLength(1);
      expect(screen.queryByRole("tab", { name: "技术面" })).not.toBeInTheDocument();
      expect(screen.queryByRole("link", { name: /返回研究维度/ })).not.toBeInTheDocument();
    },
  );

  it("redirects legacy valuation links to the profile with the historical date", async () => {
    function ProfileDestination() {
      const location = useLocation();
      return <div>{location.pathname}{location.search}{location.hash}</div>;
    }
    render(
      <MemoryRouter initialEntries={["/analysis/600519?panel=valuation&date=2026-08-20"]}>
        <Routes>
          <Route path="/analysis/:code" element={<AnalysisSections result={null} />} />
          <Route path="/stock/:code" element={<ProfileDestination />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("/stock/600519?tab=valuation&date=20260820#stock-details")).toBeVisible();
    expect(screen.queryByText("估值面内容")).not.toBeInTheDocument();
  });

  it("shows snapshot context and connects valuation navigation without replacing the report", async () => {
    const onOpenValuation = vi.fn();
    render(
      <MemoryRouter>
        <AnalysisResultSection
          result={{ stock_name: "贵州茅台", stock_code: "600519", analysis_date: "20260820" } as AnalysisResult}
          isExportingPdf={false}
          onOpenValuation={onOpenValuation}
        />
      </MemoryRouter>,
    );
    const result = screen.getByRole("region", { name: "个股分析结果" });
    expect(result).toHaveAttribute("id", "analysis-result");
    expect(result).toHaveAttribute("tabindex", "-1");
    expect(within(result).getByText("贵州茅台")).toBeVisible();
    expect(within(result).getByText("600519")).toBeVisible();
    expect(within(result).getByText("分析日期 2026-08-20")).toBeVisible();
    expect(within(result).getByRole("link", { name: /查看个股资料/ })).toHaveAttribute("href", "/stock/600519");
    fireEvent.click(await screen.findByRole("button", { name: "查看估值明细" }));
    expect(onOpenValuation).toHaveBeenCalledOnce();
    expect(screen.getByText("投资研究内容")).toBeVisible();
  });

  it("includes all dimensions and the full result exactly once when exporting a PDF", async () => {
    render(
      <MemoryRouter>
        <AnalysisSections result={{} as AnalysisResult} isExportingPdf />
      </MemoryRouter>,
    );

    expect(await screen.findByText("完整投资研究内容")).toBeVisible();
    for (const label of ["基本面", "估值面"]) {
      expect(await screen.findByText(`${label}内容`)).toBeVisible();
    }
    expect(screen.queryByText("技术面内容")).not.toBeInTheDocument();
    expect(screen.queryByText("情绪面内容")).not.toBeInTheDocument();
    expect(screen.getAllByText("综合研判内容")).toHaveLength(1);
    expect(screen.getAllByText("行动建议内容")).toHaveLength(1);
    expect(screen.getAllByText("研究结论")).toHaveLength(1);
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /返回研究维度/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/分析日期/)).not.toBeInTheDocument();
  });
});
