import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import DomesticMacroOverview from "./DomesticMacroOverview";

vi.mock("echarts-for-react/lib/core", () => ({
  default: () => <div data-testid="macro-chart" />,
}));

vi.mock("../../api/queries", () => ({
  useMacroAllData: () => ({
    data: {
      growth: {
        gdp: {
          latest: { TIME: "2026-Q2", GDP_VALUE: 320000, GDP_SAME: 5.2 },
          trend: [{ TIME: "2026-Q2", GDP_VALUE: 320000, GDP_SAME: 5.2 }],
        },
      },
      sentiment: {
        pmi: {
          latest: { TIME: "2026-07", MAKE_INDEX: 50.4, NMAKE_INDEX: 51.2 },
          trend: [{ TIME: "2026-07", MAKE_INDEX: 50.4, NMAKE_INDEX: 51.2 }],
        },
      },
      prices: {
        cpi: {
          latest: { TIME: "2026-07", NATIONAL_SAME: 0.6, NATIONAL_SEQUENTIAL: 0.2 },
          trend: [{ TIME: "2026-07", NATIONAL_SAME: 0.6 }],
        },
        ppi: {
          latest: { TIME: "2026-07", BASE_SAME: -1.2, BASE_ACCUMULATE: -1.5 },
          trend: [{ TIME: "2026-07", BASE_SAME: -1.2 }],
        },
      },
      monetary: {
        money_supply: {
          latest: { TIME: "2026-07", BASIC_CURRENCY: 3000000 },
          trend: [{ TIME: "2026-07", BASIC_CURRENCY: 3000000 }],
        },
      },
      rates: {
        lpr: {
          latest: { TIME: "2026-07", LPR1Y: 3.10, LPR5Y: 3.60 },
          trend: [{ TIME: "2026-07", LPR1Y: 3.10, LPR5Y: 3.60 }],
        },
      },
      trade: {
        exports_imports: {
          latest: { TIME: "2026-07", EXPORTS_SAME: 7.2 },
          trend: [{ TIME: "2026-07", EXPORTS_SAME: 7.2 }],
        },
      },
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

describe("DomesticMacroOverview", () => {
  it("renders the Macro Compass, key weather vanes, and charts", () => {
    render(<DomesticMacroOverview />);

    // 1. 验证宏观周期罗盘与 A 股晴雨表
    expect(screen.getByText(/宏观周期罗盘与 A 股传导晴雨表/)).toBeInTheDocument();
    expect(screen.getByText("景气扩张·动能释放期")).toBeInTheDocument();
    expect(screen.getByText("基本面与盈利双击")).toBeInTheDocument();

    // 2. 验证衍生指标（剪刀差与 PMI 荣枯）
    expect(screen.getByText("CPI-PPI 利润剪刀差")).toBeInTheDocument();
    expect(screen.getByText("📈 中下游毛利改善")).toBeInTheDocument();
    expect(screen.getByText("制造业 PMI (荣枯线)")).toBeInTheDocument();
    expect(screen.getByText("● 扩张 (先导改善)")).toBeInTheDocument();

    // 3. 验证结构化支柱走势图谱
    expect(screen.getByText("GDP 国内生产总值（季度）")).toBeInTheDocument();
    expect(screen.getByText("PMI 采购经理人指数")).toBeInTheDocument();
    expect(screen.getByText("CPI 居民消费价格指数")).toBeInTheDocument();
  });
});
