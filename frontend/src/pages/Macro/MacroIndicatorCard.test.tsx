import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MacroIndicatorCard from "./MacroIndicatorCard";

const chartMocks = vi.hoisted(() => ({
  option: null as Record<string, unknown> | null,
}));

vi.mock("echarts-for-react/lib/core", () => ({
  default: ({ option }: { option: Record<string, unknown> }) => {
    chartMocks.option = option;
    return <div data-testid="macro-chart" />;
  },
}));

describe("MacroIndicatorCard", () => {
  it("shows source, fallback, and stale metadata", () => {
    const { container } = render(
      <MacroIndicatorCard
        title="CPI"
        latest={{ TIME: "2026-07", VALUE: 0.5 }}
        trend={[]}
        fields={[{ key: "VALUE", label: "同比", unit: "%" }]}
        metadata={{
          latest: null,
          trend: [],
          source: "nbs",
          source_api: "https://data.stats.gov.cn/example",
          latest_period: "2026-07",
          is_fallback: true,
          is_stale: true,
          field_periods: { VALUE: "2025-08" },
          stale_fields: ["VALUE"],
        }}
      />,
    );

    expect(screen.getByText("国家统计局")).toBeInTheDocument();
    expect(screen.getByText("fallback")).toBeInTheDocument();
    expect(screen.getByText("数据滞后")).toBeInTheDocument();
    expect(screen.getByText("滞后")).toBeInTheDocument();
    expect(screen.getByText("2026-07")).toBeInTheDocument();
    expect(screen.getByText("数据期")).toBeInTheDocument();
    expect(container.querySelector(".macro-indicator-card__metric--rate")).toBeInTheDocument();
    expect(container.querySelector(".macro-indicator-card__metric .ant-statistic-content")).toHaveTextContent("0.50%");
  });

  it("scales large metric values into the configured display unit", () => {
    const { container } = render(
      <MacroIndicatorCard
        title="货币供应量"
        latest={{ TIME: "2026-07", BASIC_CURRENCY: 3347600 }}
        trend={[]}
        fields={[{
          key: "BASIC_CURRENCY",
          label: "M2",
          unit: "万亿元",
          precision: 2,
          valueDivisor: 10_000,
        }]}
      />,
    );

    expect(container.querySelector(".macro-indicator-card__metric--level")).toBeInTheDocument();
    expect(container.querySelector(".ant-statistic-content")).toHaveTextContent("334.76万亿元");
  });

  it("uses separate axes for level and rate series and scrolls dense legends", () => {
    render(
      <MacroIndicatorCard
        title="房地产"
        latest={{ TIME: "2026-07", VALUE: 50_000, YOY: -6.5 }}
        trend={[
          { TIME: "2026-07", VALUE: 50_000, YOY: -6.5, RATE_2: -4, RATE_3: -3, RATE_4: -2 },
          { TIME: "2026-06", VALUE: 48_000, YOY: -7, RATE_2: -5, RATE_3: -4, RATE_4: -3 },
        ]}
        fields={[
          { key: "VALUE", label: "规模", unit: "万亿元", valueDivisor: 10_000 },
          { key: "YOY", label: "同比", unit: "%" },
          { key: "RATE_2", label: "同比2", unit: "%" },
          { key: "RATE_3", label: "同比3", unit: "%" },
          { key: "RATE_4", label: "同比4", unit: "%" },
        ]}
      />,
    );

    expect(screen.getByTestId("macro-chart")).toBeInTheDocument();
    const option = chartMocks.option as {
      legend: { type: string };
      yAxis: Array<{ name?: string; position?: string }>;
      series: Array<{ name: string; yAxisIndex: number; data: number[] }>;
    };
    expect(option.legend.type).toBe("scroll");
    expect(option.yAxis).toHaveLength(2);
    expect(option.yAxis[0].name).toBe("万亿元");
    expect(option.yAxis[1]).toMatchObject({ name: "%", position: "right" });
    expect(option.series.find((item) => item.name === "规模")).toMatchObject({
      yAxisIndex: 0,
      data: [4.8, 5],
    });
    expect(option.series.find((item) => item.name === "同比")).toMatchObject({ yAxisIndex: 1 });
  });

  it("splits same-unit series onto a secondary axis when scales diverge", () => {
    render(
      <MacroIndicatorCard
        title="美国就业细项"
        latest={{ TIME: "2026-08", LEVEL: 61.6, MOM: 0.27 }}
        trend={[
          { TIME: "2026-08", LEVEL: 61.6, MOM: 0.27 },
          { TIME: "2026-07", LEVEL: 61.4, MOM: 0.16 },
        ]}
        fields={[
          { key: "LEVEL", label: "劳动参与率", unit: "%" },
          { key: "MOM", label: "平均时薪环比", unit: "%", secondaryAxis: true },
        ]}
      />,
    );

    const option = chartMocks.option as {
      yAxis: Array<{ name?: string; position?: string }>;
      series: Array<{ name: string; yAxisIndex: number }>;
    };
    expect(option.yAxis).toHaveLength(2);
    // 两组字段都是 %，左轴仍需 % 标注
    expect(option.yAxis[0].name).toBe("%");
    expect(option.yAxis[1]).toMatchObject({ name: "%", position: "right" });
    expect(option.series.find((item) => item.name === "劳动参与率")).toMatchObject({ yAxisIndex: 0 });
    expect(option.series.find((item) => item.name === "平均时薪环比")).toMatchObject({ yAxisIndex: 1 });
  });

  it("keeps a single axis when every same-unit series is forced to the primary axis", () => {
    render(
      <MacroIndicatorCard
        title="同量级"
        latest={{ TIME: "2026-08", A: 3.1, B: 2.4 }}
        trend={[{ TIME: "2026-08", A: 3.1, B: 2.4 }]}
        fields={[
          { key: "A", label: "同比", unit: "%", secondaryAxis: false },
          { key: "B", label: "核心同比", unit: "%" },
        ]}
      />,
    );

    const option = chartMocks.option as {
      yAxis: Array<{ name?: string }> | { name?: string };
      series: Array<{ name: string; yAxisIndex: number }>;
    };
    expect(Array.isArray(option.yAxis)).toBe(false);
    expect(option.series.every((item) => item.yAxisIndex === 0)).toBe(true);
  });
});
