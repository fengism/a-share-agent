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
        onPush={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "分析历史" }));

    expect(onShowHistory).toHaveBeenCalledOnce();
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
        onPush={onPush}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /^推\s*送$/ }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /推送/ }));

    await waitFor(() => expect(onPush).toHaveBeenCalledOnce());
    expect(dialog).toBeInTheDocument();
  });
});
