import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NationalTeam from ".";

const mocks = vi.hoisted(() => ({
  refetch: vi.fn(),
  useNationalTeamHoldings: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useNationalTeamHoldings: (days: number) => mocks.useNationalTeamHoldings(days),
}));

vi.mock("echarts-for-react/lib/core", () => ({
  default: ({ option }: {
    option: {
      title?: { text?: string };
      yAxis?: unknown[];
      legend?: { show?: boolean };
      series?: Array<{
        lineStyle?: { color?: string; type?: string };
        showSymbol?: boolean;
        symbolSize?: number;
      }>;
    };
  }) => (
    <div
      data-testid="national-team-chart"
      data-title={option.title?.text}
      data-y-axes={option.yAxis?.length ?? 0}
      data-legend-visible={String(option.legend?.show !== false)}
      data-series-colors={option.series?.map((series) => series.lineStyle?.color).join(",")}
      data-series-line-types={option.series?.map((series) => series.lineStyle?.type).join(",")}
      data-series-show-symbol={option.series?.map((series) => String(series.showSymbol)).join(",")}
      data-series-symbol-size={option.series?.map((series) => String(series.symbolSize)).join(",")}
    />
  ),
}));

const indexNames = ["沪深300", "上证50", "中证500", "中证1000", "科创50", "创业板"];
const etfs = [
  ["510300", "沪深300ETF华泰柏瑞", "华泰柏瑞基金", "沪深300"],
  ["510310", "沪深300ETF易方达", "易方达基金", "沪深300"],
  ["510330", "沪深300ETF华夏", "华夏基金", "沪深300"],
  ["159919", "沪深300ETF嘉实", "嘉实基金", "沪深300"],
  ["510050", "上证50ETF华夏", "华夏基金", "上证50"],
  ["510500", "中证500ETF南方", "南方基金", "中证500"],
  ["512100", "中证1000ETF南方", "南方基金", "中证1000"],
  ["159845", "中证1000ETF华夏", "华夏基金", "中证1000"],
  ["560010", "中证1000ETF广发", "广发基金", "中证1000"],
  ["159629", "中证1000ETF富国", "富国基金", "中证1000"],
  ["588080", "科创50ETF易方达", "易方达基金", "科创50"],
  ["159915", "创业板ETF易方达", "易方达基金", "创业板"],
].map(([code, name, fund_manager, index_name], order) => ({
  code,
  name,
  fund_manager,
  index_name,
  index_key: `index-${order}`,
  exchange: code.startsWith("5") ? "SH" : "SZ",
  latest_date: "2026-09-16",
  latest_shares_100m: 100 + order,
  latest_change_1d_100m: order % 2 === 0 ? 1.2 : -0.8,
  change_5d_100m: 2.4,
  change_20d_100m: 5.6,
  points: [],
}));

const data = {
  requested_days: 120,
  as_of_date: "2026-09-16",
  fetched_at: "2026-09-17T19:00:00+08:00",
  source: "上交所/深交所/东方财富",
  disclaimer: "ETF 份额变化仅作为代理指标，不等于中央汇金真实持仓。",
  methodology: "逐只 ETF 份额变化乘以 ETF 收盘价，再按宽基汇总。",
  partial: true,
  missing_etfs: ["159629"],
  missing_share_etfs: ["159629"],
  missing_price_etfs: [],
  missing_indices: [],
  covered_etf_count: 11,
  total_etf_count: 12,
  stale: false,
  calendar_degraded: false,
  refreshing: false,
  observations: [],
  summary: {
    total_shares_100m: 1234.56,
    change_1d_100m: 12.34,
    change_5d_100m: 23.45,
    change_20d_100m: 45.67,
    estimated_net_flow_1d_100m: 8.9,
    estimated_net_flow_5d_100m: 18.9,
    estimated_net_flow_20d_100m: 38.9,
  },
  indices: indexNames.map((index_name, index) => ({
    index_key: `index-${index}`,
    index_name,
    index_code: `00000${index}.SH`,
    etf_codes: etfs.filter((item) => item.index_name === index_name).map((item) => item.code),
    covered_etf_codes: etfs.filter((item) => item.index_name === index_name && item.code !== "159629").map((item) => item.code),
    latest_date: "2026-09-16",
    latest_total_shares_100m: 200 + index,
    latest_change_1d_100m: index - 2,
    change_5d_100m: index + 1,
    change_20d_100m: index + 4,
    estimated_net_flow_1d_100m: index - 1,
    points: [
      {
        date: "2026-09-15",
        total_shares_100m: 198 + index,
        shares_change_100m: 1,
        cumulative_change_100m: 0,
        estimated_net_flow_100m: 2,
        index_close: 3500 + index * 100,
      },
      {
        date: "2026-09-16",
        total_shares_100m: 200 + index,
        shares_change_100m: 2,
        cumulative_change_100m: 2,
        estimated_net_flow_100m: 3,
        index_close: 3520 + index * 100,
      },
    ],
  })),
  etfs,
};

describe("NationalTeam page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useNationalTeamHoldings.mockImplementation(() => ({
      data,
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: mocks.refetch,
    }));
  });

  it("renders proxy disclosure, summary, six independent dual-axis charts, and all ETFs", () => {
    render(<NationalTeam />);

    expect(screen.getByRole("heading", { name: "国家队" })).toBeInTheDocument();
    expect(screen.getByText(/不等于中央汇金真实持仓/)).toBeInTheDocument();
    expect(screen.getByText(/数据不完整/)).toBeInTheDocument();

    // Toggle details to view full description
    fireEvent.click(screen.getByRole("button", { name: /查看明细/ }));
    expect(screen.getByText(/份额缺失或区间不完整/)).toBeInTheDocument();
    expect(screen.getByText(/不代表零变化/)).toBeInTheDocument();
    expect(screen.getAllByText(/159629/).length).toBeGreaterThan(0);
    expect(screen.getByText("1,234.56 亿份")).toBeInTheDocument();
    expect(screen.getByText(new RegExp("覆盖 11/12 只宽基 ETF"))).toBeInTheDocument();
    expect(screen.getByText("覆盖 3/4 只")).toBeInTheDocument();

    const charts = screen.getAllByTestId("national-team-chart");
    expect(charts).toHaveLength(6);
    for (const chart of charts) {
      expect(chart).toHaveAttribute("data-y-axes", "2");
      expect(chart).toHaveAttribute("data-legend-visible", "false");
      expect(chart).toHaveAttribute("data-series-line-types", "solid,dashed");
      const seriesColors = chart.getAttribute("data-series-colors")?.split(",") ?? [];
      expect(seriesColors).toHaveLength(2);
      expect(seriesColors[0]).not.toBe(seriesColors[1]);
    }
    expect(screen.getAllByLabelText(/图例$/)).toHaveLength(6);
    expect(screen.getAllByText("ETF 合计份额")).toHaveLength(6);
    for (const indexName of indexNames) {
      expect(screen.getByRole("heading", { name: indexName })).toBeInTheDocument();
    }
    for (const etf of etfs) {
      expect(screen.getAllByText(etf.code).length).toBeGreaterThan(0);
    }
  });

  it("shows point markers and a history notice when only one share point is available", () => {
    const onePointData = {
      ...data,
      indices: data.indices.map((item, index) => (
        index === 5 ? { ...item, points: item.points.slice(-1) } : item
      )),
    };
    mocks.useNationalTeamHoldings.mockImplementation(() => ({
      data: onePointData,
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: mocks.refetch,
    }));

    render(<NationalTeam />);

    const chinextChart = screen.getAllByTestId("national-team-chart")[5];
    expect(chinextChart).toHaveAttribute("data-series-show-symbol", "true,true");
    expect(chinextChart).toHaveAttribute("data-series-symbol-size", "7,7");
    expect(screen.getByText(/当前仅有 1 个份额点/)).toBeInTheDocument();
  });

  it("shows the actual index date and unknown changes instead of a false zero", () => {
    mocks.useNationalTeamHoldings.mockReturnValue({
      data: {
        ...data,
        indices: data.indices.map((item) => ({
          ...item,
          latest_date: "2026-09-15",
          latest_change_1d_100m: null,
          change_5d_100m: null,
          change_20d_100m: null,
        })),
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: mocks.refetch,
    });

    render(<NationalTeam />);

    expect(screen.getAllByText("截至 2026-09-15")).toHaveLength(6);
    expect(screen.getAllByText("1日 -")).toHaveLength(6);
    expect(screen.queryByText("1日 0.00 亿份")).not.toBeInTheDocument();
  });

  it("does not rank or draw a positive bar for unknown changes", () => {
    mocks.useNationalTeamHoldings.mockReturnValue({
      data: {
        ...data,
        indices: data.indices.slice(0, 3).map((item, index) => ({
          ...item,
          change_20d_100m: [null, -2, 0][index],
        })),
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: mocks.refetch,
    });

    const { container } = render(<NationalTeam />);
    const rows = container.querySelectorAll(".national-team-rotation__item");
    expect(rows).toHaveLength(3);
    expect(rows[0].querySelector(".national-team-rotation__name")).toHaveTextContent("中证500");
    expect(rows[1].querySelector(".national-team-rotation__name")).toHaveTextContent("上证50");
    expect(rows[2].querySelector(".national-team-rotation__name")).toHaveTextContent("沪深300");
    expect(rows[0].querySelector(".national-team-rotation__rank")).toHaveTextContent("1");
    expect(rows[0].querySelector(".national-team-rotation__val")).toHaveTextContent("0.00");
    expect(rows[2].querySelector(".national-team-rotation__rank")).toHaveTextContent("-");
    expect(rows[2].querySelector(".national-team-rotation__bar span")).not.toBeInTheDocument();
    expect(rows[2].querySelector(".national-team-rotation__val")).toHaveTextContent("数据不足");
  });

  it("requests the selected history window and refreshes on demand", () => {
    render(<NationalTeam />);

    expect(mocks.useNationalTeamHoldings).toHaveBeenLastCalledWith(120);
    fireEvent.click(screen.getByRole("radio", { name: "240 天" }));
    expect(mocks.useNationalTeamHoldings).toHaveBeenLastCalledWith(240);

    fireEvent.click(screen.getByRole("button", { name: /刷新/ }));
    expect(mocks.refetch).toHaveBeenCalledTimes(1);
  });

  it("allows switching the rotation ranking timeframe and filtering ETF table by broad-based index", () => {
    render(<NationalTeam />);

    expect(screen.getByText("结构轮动 · 20 日份额变化")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "5 日" }));
    expect(screen.getByText("结构轮动 · 5 日份额变化")).toBeInTheDocument();

    const link510300 = screen.getByRole("link", { name: "510300" });
    expect(link510300).toHaveAttribute("href", "/stock/510300");

    // Filter ETF table to 沪深300
    fireEvent.click(screen.getByRole("radio", { name: /沪深300 \(4\)/ }));
    expect(screen.getByText("510300")).toBeInTheDocument();
    expect(screen.queryByText("588080")).not.toBeInTheDocument();

    // Switch back to All
    fireEvent.click(screen.getByRole("radio", { name: /全部 \(12\)/ }));
    expect(screen.getByText("588080")).toBeInTheDocument();

    // Search by ETF code or manager
    const searchInput = screen.getByPlaceholderText("搜索代码 / 名称 / 基金公司");
    fireEvent.change(searchInput, { target: { value: "华夏" } });
    expect(screen.getByText("510330")).toBeInTheDocument();
    expect(screen.queryByText("510310")).not.toBeInTheDocument();

    // Clear search
    fireEvent.change(searchInput, { target: { value: "" } });
    expect(screen.getByText("510310")).toBeInTheDocument();
  });
});


describe("NationalTeam data quality", () => {
  it("shows verified source, business date and fetch time on the date tooltip", async () => {
    mocks.useNationalTeamHoldings.mockReturnValue({
      data: {
        ...data, partial: false,
        etfs: data.etfs.map((item, index) => ({
          ...item,
          points: index === 0 ? [{ date: item.latest_date, source: "sse_history", verification_status: "verified", fetched_at: "2026-09-17T08:00:00+00:00", shares_100m: 100 }] : [],
        })),
      },
      isLoading: false, isFetching: false, error: null, refetch: mocks.refetch,
    });
    const { container } = render(<NationalTeam />);
    expect(screen.queryByText("数据不完整")).not.toBeInTheDocument();
    fireEvent.mouseOver(container.querySelector(".national-team-date")!);
    const tooltip = await screen.findByRole("tooltip");
    expect(tooltip).toHaveTextContent("来源：上交所历史份额");
    expect(tooltip).toHaveTextContent("业务日期：2026-09-16");
    expect(tooltip).toHaveTextContent("抓取时间：2026-09-17T08:00:00+00:00");
    expect(tooltip).toHaveTextContent("日期已确认");
  });

  it("distinguishes background refresh, freshness, calendar and price gaps", () => {
    mocks.useNationalTeamHoldings.mockReturnValue({
      data: {
        ...data, refreshing: true, stale: true, calendar_degraded: true,
        expected_date: "2026-09-18", covered_etf_count: 8,
        missing_price_etfs: ["510300"], missing_indices: ["index-0"],
        observations: [{ code: "159915", source: "szse_current", shares_100m: 999, business_date: null, verification_status: "provisional", fetched_at: data.fetched_at }],
      },
      isLoading: false, isFetching: false, error: null, refetch: mocks.refetch,
    });
    render(<NationalTeam />);
    expect(screen.getByText("数据不完整 · 后台更新中")).toBeInTheDocument();
    expect(screen.getByText(new RegExp("覆盖 8/12 只宽基 ETF"))).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /查看明细/ }));
    const alert = screen.getByText("数据不完整 · 后台更新中").closest(".national-team-partial-alert");
    expect(alert).toHaveTextContent("预期交易日 2026-09-18");
    expect(alert).toHaveTextContent("交易日历暂不可用");
    expect(alert).toHaveTextContent("ETF 行情缺失：510300");
    expect(alert).toHaveTextContent("指数行情缺失：沪深300");
    expect(alert).toHaveTextContent("不计入历史与资金估算");
  });

  it("supports exporting ETF data to CSV and previewing dual-axis chart modal", () => {
    render(<NationalTeam />);

    const exportBtn = screen.getByRole("button", { name: /导出 CSV/ });
    expect(exportBtn).toBeInTheDocument();

    const expandBtns = screen.getAllByRole("button", { name: "放大查看大图" });
    expect(expandBtns.length).toBeGreaterThan(0);
    fireEvent.click(expandBtns[0]);

    expect(screen.getByText(/份额与指数走势大图/)).toBeInTheDocument();
  });
});
