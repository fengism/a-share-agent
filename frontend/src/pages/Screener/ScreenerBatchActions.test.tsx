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

  it("renders and triggers AI diagnosis when onAiDiagnose is provided", () => {
    const aiDiagnose = vi.fn();
    render(
      <ScreenerBatchActions
        selectedCodes={["600519", "000858"]}
        isAddingWatchlist={false}
        isAnalyzing={false}
        analysisProgress=""
        onAddWatchlist={vi.fn()}
        onAnalyze={vi.fn()}
        onBacktest={vi.fn()}
        onClear={vi.fn()}
        onAiDiagnose={aiDiagnose}
      />,
    );

    const btn = screen.getByRole("button", { name: /AI 诊断/ });
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(aiDiagnose).toHaveBeenCalledOnce();
  });
});
