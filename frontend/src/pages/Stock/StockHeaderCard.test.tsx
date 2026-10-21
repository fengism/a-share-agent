import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import StockHeaderCard from "./StockHeaderCard";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

describe("StockHeaderCard", () => {
  it("renders CN stock header with price, industry, concepts and analysis button", () => {
    const handleToggle = vi.fn();
    render(
      <MemoryRouter>
        <StockHeaderCard
          info={{
            code: "600519",
            name: "贵州茅台",
            current_price: 1800.5,
            first_industry: { code: "B", name: "食品饮料" },
            concepts: [{ code: "C1", name: "白酒概念" }],
            turnover_pct: 0.45,
          }}
          isWatched={false}
          isWatchlistPending={false}
          onToggleWatchlist={handleToggle}
          changePct={1.25}
          market="cn"
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("公司概览")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "贵州茅台" })).toBeInTheDocument();
    expect(screen.getByText("600519")).toBeInTheDocument();
    expect(screen.getByText("¥1800.50")).toBeInTheDocument();
    expect(screen.getByText("+1.25% · 换手 0.45%")).toBeInTheDocument();
    expect(screen.getByText("食品饮料")).toBeInTheDocument();
    expect(screen.getByText("白酒概念")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "加入自选" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "进入 AI 分析" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "加入自选" }));
    expect(handleToggle).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "进入 AI 分析" }));
    expect(mocks.navigate).toHaveBeenCalledWith("/analysis/600519");
  });

  it("renders HK stock header with HK$ currency, English name and trading rules tag", () => {
    const handleToggle = vi.fn();
    render(
      <MemoryRouter>
        <StockHeaderCard
          info={{
            code: "00700",
            name: "腾讯控股",
            current_price: 385.4,
          }}
          isWatched={true}
          isWatchlistPending={false}
          onToggleWatchlist={handleToggle}
          changePct={2.17}
          changeAmount={8.2}
          englishName="TENCENT"
          market="hk"
          showAnalysisButton={false}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("港股概览 · 香港联合交易所")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "腾讯控股" })).toBeInTheDocument();
    expect(screen.getByText("00700")).toBeInTheDocument();
    expect(screen.getByText("HK$385.40")).toBeInTheDocument();
    expect(screen.getByText("+8.20 (+2.17%)")).toBeInTheDocument();
    expect(screen.getByText("港股主板")).toBeInTheDocument();
    expect(screen.getByText("TENCENT")).toBeInTheDocument();
    expect(screen.getByText("港币 (HKD)")).toBeInTheDocument();
    expect(screen.getByText("T+0 回转交易")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "移出自选" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "进入 AI 分析" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "移出自选" }));
    expect(handleToggle).toHaveBeenCalledTimes(1);
  });
});
