import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import FinanceTab from "./FinanceTab";

vi.mock("../../api/queries", () => ({
  useMacroAllData: () => ({
    data: {
      monetary: {
        money_supply: {
          latest: {
            TIME: "2026-08",
            BASIC_CURRENCY: 3000000,
            CURRENCY: 650000,
            FREE_CASH: 110000,
          },
          trend: [],
          source: "pbc",
        },
        social_financing: {
          latest: {
            TIME: "2026-08",
            SOCIAL_FINANCING_INCREMENT: 28000,
            RMB_LOAN: 15000,
            GOVERNMENT_BOND: 8000,
            CORPORATE_BOND: 3000,
          },
          trend: [],
          source: "pbc",
        },
      },
      rates: {
        lpr: {
          latest: {
            TIME: "2026-08",
            LPR1Y: 3.1,
            LPR5Y: 3.6,
          },
          trend: [],
          source: "pbc",
        },
        shibor: {
          latest: {
            TIME: "2026-08",
            MONTH3: 1.85,
            MONTH6: 1.9,
            MONTH9: 1.95,
            YEAR1: 2.0,
          },
          trend: [],
          source: "shibor",
        },
      },
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

describe("FinanceTab", () => {
  it("renders monetary supply, LPR interest rates, and liquidity cards", () => {
    render(<FinanceTab />);

    expect(screen.getByText("💡 宏观金融与货币流动性环境总览")).toBeInTheDocument();
    expect(screen.getByText("广义货币 M2 总量")).toBeInTheDocument();
    expect(screen.getByText("1年期 LPR (短端贷款)")).toBeInTheDocument();
    expect(screen.getByText("5年期以上 LPR (长端贷款)")).toBeInTheDocument();
    expect(screen.getByText("LPR 期限利差 (5Y - 1Y)")).toBeInTheDocument();
    expect(screen.getByText("货币供应量 M0/M1/M2（万亿元）")).toBeInTheDocument();
    expect(screen.getByText("社会融资规模")).toBeInTheDocument();
    expect(screen.getByText("LPR 贷款市场报价利率")).toBeInTheDocument();
    expect(screen.getByText("SHIBOR 上海银行间同业拆放利率")).toBeInTheDocument();
  });
});
