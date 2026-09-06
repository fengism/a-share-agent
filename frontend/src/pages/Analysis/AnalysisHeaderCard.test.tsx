import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AnalysisPageData, AnalysisResult } from "../../types/stock";
import AnalysisHeaderCard from "./AnalysisHeaderCard";

const pageData: AnalysisPageData = {
  stock_info: null,
  kline: null,
  intraday: null,
  valuation: null,
  cached_analysis: null,
  key_levels: null,
  chip_distribution: null,
};

describe("AnalysisHeaderCard", () => {
  it("keeps analysis history reachable from the detail page", () => {
    const onShowHistory = vi.fn();
    render(
      <AnalysisHeaderCard
        code="600519"
        pageData={pageData}
        result={null}
        isAnalyzing={false}
        isPushing={false}
        isWatched={false}
        isWatchlistPending={false}
        onToggleWatchlist={vi.fn()}
        onAnalyze={vi.fn()}
        onCancel={vi.fn()}
        onExportPdf={vi.fn()}
        onShowHistory={onShowHistory}
        onOpenResearchReport={vi.fn()}
        onPush={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "研究历史" }));

    expect(onShowHistory).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "开始研究" })).toBeInTheDocument();
  });

  it("prefers the latest intraday quote over the completed daily K-line", () => {
    render(
      <AnalysisHeaderCard
        code="600519"
        pageData={{
          ...pageData,
          kline: {
            code: "600519",
            period: "daily",
            adjust: "qfq",
            items: [{
              date: "2026-08-26",
              open: 1510,
              close: 1520,
              high: 1525,
              low: 1508,
              volume: 100,
              amount: 152_000,
              amplitude: 1,
              turnover_pct: 0.2,
              change_pct: 0.66,
            }],
          },
        }}
        intradayData={{
          code: "600519",
          source: "mock",
          prev_close: 1520,
          items: [{
            time: "10:30",
            price: 1535.2,
            avg_price: 1530,
            volume: 20,
            amount: 30_704,
            change_pct: 1,
          }],
        }}
        result={null}
        isAnalyzing={false}
        isPushing={false}
        isWatched={false}
        isWatchlistPending={false}
        onToggleWatchlist={vi.fn()}
        onAnalyze={vi.fn()}
        onCancel={vi.fn()}
        onExportPdf={vi.fn()}
        onShowHistory={vi.fn()}
        onOpenResearchReport={vi.fn()}
        onPush={vi.fn()}
      />,
    );

    expect(screen.getByText("¥1535.20")).toBeInTheDocument();
    expect(screen.getByText("+1.00%")).toBeInTheDocument();
    expect(screen.queryByText("¥1520.00")).not.toBeInTheDocument();
  });

  it("keeps the push modal open when pushing fails", async () => {
    const onPush = vi.fn().mockResolvedValue(false);
    render(
      <AnalysisHeaderCard
        code="600519"
        pageData={pageData}
        result={{} as AnalysisResult}
        isAnalyzing={false}
        isPushing={false}
        isWatched={false}
        isWatchlistPending={false}
        onToggleWatchlist={vi.fn()}
        onAnalyze={vi.fn()}
        onCancel={vi.fn()}
        onExportPdf={vi.fn()}
        onShowHistory={vi.fn()}
        onOpenResearchReport={vi.fn()}
        onPush={onPush}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /^推\s*送$/ }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /推送/ }));

    await waitFor(() => expect(onPush).toHaveBeenCalledOnce());
    expect(dialog).toBeInTheDocument();
  });

  it("opens the focused investment research report when analysis exists", () => {
    const onOpenResearchReport = vi.fn();
    render(
      <AnalysisHeaderCard
        code="600519"
        pageData={pageData}
        result={{} as AnalysisResult}
        isAnalyzing={false}
        isPushing={false}
        isWatched={false}
        isWatchlistPending={false}
        onToggleWatchlist={vi.fn()}
        onAnalyze={vi.fn()}
        onCancel={vi.fn()}
        onExportPdf={vi.fn()}
        onShowHistory={vi.fn()}
        onOpenResearchReport={onOpenResearchReport}
        onPush={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "打开报告模式" }));

    expect(onOpenResearchReport).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "更新研究" })).toBeInTheDocument();
  });
});
