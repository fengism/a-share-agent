import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AiNaturalScreenerBar, parseNaturalLanguageToFilters } from "./AiNaturalScreenerBar";
import { DEFAULT_SCREENER_FILTERS } from "../../features/screener/screenerUrlState";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock("antd", async (importOriginal) => {
  const actual = await importOriginal<typeof import("antd")>();
  return {
    ...actual,
    message: {
      info: vi.fn(),
      success: vi.fn(),
      warning: vi.fn(),
    },
  };
});

describe("parseNaturalLanguageToFilters", () => {
  it("correctly extracts valuation, market cap, and anomaly constraints", () => {
    const text = "市值大于500亿、PE小于20、破净、换手率大于5%、剔除ST";
    const { patch, matchedExplanations } = parseNaturalLanguageToFilters(
      text,
      ["电子", "银行"],
      ["高股息", "半导体"]
    );

    expect(patch.market_cap_min).toBe(500);
    expect(patch.pe_max).toBe(20);
    expect(patch.is_broken_net).toBe(true);
    expect(patch.pb_max).toBe(1.0);
    expect(patch.turnover_pct_min).toBe(5);
    expect(patch.exclude_st).toBe(true);
    expect(matchedExplanations.length).toBeGreaterThanOrEqual(4);
  });

  it("extracts matching industries and concepts when present", () => {
    const text = "寻找半导体概念的电子行业成长股，涨幅大于3%";
    const { patch } = parseNaturalLanguageToFilters(
      text,
      ["电子", "计算机"],
      ["半导体", "新能源"]
    );

    expect(patch.industries).toEqual(["电子"]);
    expect(patch.concepts).toEqual(["半导体"]);
    expect(patch.change_pct_min).toBe(3);
  });
});

describe("AiNaturalScreenerBar Component", () => {
  it("renders input, handles preset tag click, and triggers filter patch", () => {
    const onApply = vi.fn();
    const onSearch = vi.fn();

    render(
      <AiNaturalScreenerBar
        currentFilters={DEFAULT_SCREENER_FILTERS}
        onApplyFilters={onApply}
        onSearch={onSearch}
      />
    );

    expect(screen.getByText("AI 语义选股助手")).toBeInTheDocument();

    // 点击预设灵感标签
    const presetTag = screen.getByText("市值大于500亿、PE小于20的高股息蓝筹");
    fireEvent.click(presetTag);

    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({
        market_cap_min: 500,
        pe_max: 20,
      })
    );
    expect(onSearch).toHaveBeenCalled();
  });

  it("navigates to Chat when clicking 问 AI 选股", () => {
    mockNavigate.mockClear();
    render(
      <AiNaturalScreenerBar
        currentFilters={DEFAULT_SCREENER_FILTERS}
        onApplyFilters={vi.fn()}
        onSearch={vi.fn()}
      />
    );

    const askBtn = screen.getByRole("button", { name: /问 AI 选股/ });
    fireEvent.click(askBtn);

    expect(mockNavigate).toHaveBeenCalledWith(
      expect.stringContaining("/chat?prompt=")
    );
  });
});
