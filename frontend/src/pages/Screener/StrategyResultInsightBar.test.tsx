import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import StrategyResultInsightBar from "./StrategyResultInsightBar";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

describe("StrategyResultInsightBar", () => {
  it("renders hit rate, win rate, and fresh signal stats correctly", () => {
    const onSelectAll = vi.fn();
    const onBacktest = vi.fn();

    render(
      <StrategyResultInsightBar
        strategyName="多头突破"
        matchedCodes={["600519", "000858", "300750"]}
        evaluated={10}
        returnsSinceSignal={new Map([
          ["600519", 5.2],
          ["000858", 2.1],
          ["300750", -1.5],
        ])}
        signalAges={new Map([
          ["600519", 2],
          ["000858", 5],
          ["300750", 1],
        ])}
        onSelectAllMatched={onSelectAll}
        onBacktestAll={onBacktest}
      />
    );

    expect(screen.getByText(/扫描命中:/)).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText(/30\.0%/)).toBeInTheDocument();
    expect(screen.getByText("67%")).toBeInTheDocument(); // 2/3 胜率
    expect(screen.getByText(/近3日新信号:/)).toBeInTheDocument();

    // 勾选前10只
    fireEvent.click(screen.getByRole("button", { name: /勾选前10只/ }));
    expect(onSelectAll).toHaveBeenCalledOnce();

    // 批量回测
    fireEvent.click(screen.getByRole("button", { name: /批量回测/ }));
    expect(onBacktest).toHaveBeenCalledOnce();
  });

  it("handles AI review button click", () => {
    mockNavigate.mockClear();
    render(
      <StrategyResultInsightBar
        strategyName="低估突破"
        matchedCodes={["600519"]}
        evaluated={5}
        returnsSinceSignal={new Map([["600519", 3.0]])}
        signalAges={new Map([["600519", 1]])}
      />
    );

    const btn = screen.getByRole("button", { name: /AI 策略战术复盘/ });
    fireEvent.click(btn);
    expect(mockNavigate).toHaveBeenCalledWith(
      expect.stringContaining("/chat?prompt=")
    );
  });

  it("returns null when matchedCodes is empty", () => {
    const { container } = render(
      <StrategyResultInsightBar
        strategyName="测试"
        matchedCodes={[]}
        evaluated={0}
        returnsSinceSignal={new Map()}
        signalAges={new Map()}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });
});
