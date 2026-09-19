import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ScreenerBatchActions from "./ScreenerBatchActions";

describe("ScreenerBatchActions", () => {
  it("removes stock comparison while preserving analysis and backtest actions", () => {
    const backtest = vi.fn();
    render(
      <ScreenerBatchActions
        selectedCodes={["1", "2", "3", "4", "5", "6"]}
        isAddingWatchlist={false}
        isAnalyzing={false}
        analysisProgress=""
        onAddWatchlist={vi.fn()}
        onAnalyze={vi.fn()}
        onBacktest={backtest}
        onClear={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: /批量对比/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /批量分析/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: /批量回测/ }));
    expect(backtest).toHaveBeenCalledOnce();
  });
});
