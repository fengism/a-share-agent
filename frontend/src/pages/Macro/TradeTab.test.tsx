import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import TradeTab from "./TradeTab";

vi.mock("../../api/queries", () => ({
  useMacroAllData: () => ({
    data: {
      trade: {
        exports_imports: {
          latest: {
            TIME: "2026-07",
            EXPORTS_SAME: 7.0,
            IMPORTS_SAME: 7.2,
          },
          trend: [],
          source: "customs",
        },
        balance: {
          latest: {
            TIME: "2026-07",
            BALANCE: 846.5,
          },
          trend: [],
          source: "customs",
        },
      },
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useCustomsTradeData: () => ({
    data: {
      matched_commodity_profiles: [
        {
          commodity: "电动汽车",
          trade_type: "出口",
          category: "机电产品",
          unit: "辆",
          key_target_markets: "欧洲、东南亚",
          related_a_stocks: ["比亚迪", "长城汽车"],
          description: "新能源汽车整车出海重点品类",
        },
      ],
    },
  }),
}));

describe("TradeTab", () => {
  it("renders export/import indicators and commodity references", () => {
    render(<TradeTab />);

    expect(screen.getByText("💡 进出口景气与出海产业链研判")).toBeInTheDocument();
    expect(screen.getByText("全国出口增速 (月同比)")).toBeInTheDocument();
    expect(screen.getByText("全国进口增速 (月同比)")).toBeInTheDocument();
    expect(screen.getByText("单月贸易顺差 (亿美元)")).toBeInTheDocument();
    expect(screen.getByText("进出口同比增速")).toBeInTheDocument();
    expect(screen.getAllByText("贸易差额").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("重点商品与关联公司参考（静态资料）")).toBeInTheDocument();
    expect(screen.getByText("电动汽车")).toBeInTheDocument();
    expect(screen.getByText("比亚迪")).toBeInTheDocument();
  });
});
