import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NationalTeam from ".";

const mocks = vi.hoisted(() => ({
  refetch: vi.fn(),
  useNationalTeamHoldings: vi.fn(),
  useNationalTeamBacktest: vi.fn(),
  useNationalTeamIndexSeriesItem: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useNationalTeamHoldings: (days: number) => mocks.useNationalTeamHoldings(days),
  useNationalTeamBacktest: (days: number) => mocks.useNationalTeamBacktest(days),
  useNationalTeamIndexSeriesItem: (indexKey: string, days: number) => mocks.useNationalTeamIndexSeriesItem(indexKey, days),
}));

vi.mock("echarts-for-react/lib/core", () => ({
  default: ({ option, ...rest }: {
    option: {
      title?: { text?: string };
      yAxis?: unknown[] | unknown;
      legend?: { show?: boolean };
      series?: Array<{
        lineStyle?: { color?: string; type?: string };
        showSymbol?: boolean;
        symbolSize?: number;
      }>;
    };
    [key: string]: unknown;
  }) => (
    <div
      data-testid={(rest["data-testid"] as string) || "national-team-chart"}
      data-title={option.title?.text}
      data-y-axes={Array.isArray(option.yAxis) ? option.yAxis.length : (option.yAxis ? 1 : 0)}
      data-legend-visible={String(option.legend?.show !== false)}
      data-series-colors={option.series?.map((series) => series.lineStyle?.color).join(",")}
      data-series-line-types={option.series?.map((series) => series.lineStyle?.type).join(",")}
      data-series-show-symbol={option.series?.map((series) => String(series.showSymbol)).join(",")}
      data-series-symbol-size={option.series?.map((series) => String(series.symbolSize)).join(",")}
    />
  ),
}));

const renderPage = (ui = <NationalTeam />, initialEntries = ["/?tab=all"]) =>
  render(<MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>);

const mockIndexSeries = (indices: unknown[]) => {
  mocks.useNationalTeamIndexSeriesItem.mockImplementation((indexKey: string) => ({
    data: (indices as typeof data.indices).find((item) => item.index_key === indexKey),
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }));
};

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
  category: (index_name === "沪深300" || index_name === "上证50") ? "core_broad" : "growth",
  index_key: `index-${order}`,
  exchange: code.startsWith("5") ? "SH" : "SZ",
  latest_date: "2026-09-16",
  latest_shares_100m: 100 + order,
  latest_change_1d_100m: order % 2 === 0 ? 1.2 : -0.8,
  change_5d_100m: 2.4,
  change_20d_100m: 5.6,
  latest_amount_100m: order === 0 ? 32.5 : 5.0,
  // 后端 include_etf_points=false 时不再返回 points，表格靠这个标量字段。
  latest_estimated_net_flow_100m: order === 0 ? 12.5 : -2.5,
  volume_ratio: order === 0 ? 2.5 : 1.1,
  is_abnormal_volume: order === 0,
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
  daily_flows: [
    {
      date: "2026-09-15",
      total_flow_100m: 15.2,
      total_shares_change_100m: 8.5,
      flows_by_index: { csi300: 10.0, sz50: 5.2 },
      flows_by_category: { core_broad: 15.2, a500: 0, growth: 0, dividend: 0 },
    },
    {
      date: "2026-09-16",
      total_flow_100m: -3.5,
      total_shares_change_100m: -2.1,
      flows_by_index: { csi300: -2.0, sz50: -1.5 },
      flows_by_category: { core_broad: -3.5, a500: 0, growth: 0, dividend: 0 },
    },
  ],
  support_score: {
    score: 68.5,
    status: "active" as const,
    label: "积极托底",
    description: "主力资金在重点战略宽基上呈现持续净买入，有效构筑下方防线。",
    net_flow_factor: 25.5,
    breadth_factor: 22.0,
    divergence_factor: 21.0,
    confidence: 0.86,
    percentile_60d: 82.5,
  },
  support_score_history: [
    { date: "2026-09-10", score: 52.0, status: "moderate" as const, confidence: 0.9, coverage_ratio: 1.0 },
    { date: "2026-09-11", score: 55.0, status: "moderate" as const, confidence: 0.9, coverage_ratio: 1.0 },
    { date: "2026-09-12", score: 61.0, status: "active" as const, confidence: 0.86, coverage_ratio: 1.0 },
    { date: "2026-09-15", score: 68.5, status: "active" as const, confidence: 0.86, coverage_ratio: 1.0 },
  ],
  milestones: [
    {
      date: "2024-02-06",
      title: "汇金扩大增持范围并加大力度",
      type: "policy" as const,
      description: "中央汇金公告充分认可当前A股配置价值，扩大增持范围。",
      index_points: { "沪深300": 3316.33 },
    },
  ],
  support_zones: [
    {
      index_key: "csi300",
      index_name: "沪深300",
      current_price: 3850.0,
      weighted_avg_cost: 3600.0,
      cost_buffer_pct: 6.94,
      zones: [
        { range_label: "3400-3600", net_flow_100m: 120.0, share_pct: 60.0 },
        { range_label: "3600-3800", net_flow_100m: 80.0, share_pct: 40.0 },
      ],
    },
  ],
  portrait: {
    reporting_period: "2024年报 / 2024Q3权威公告",
    total_market_value_trillion: 3.85,
    entities: [
      {
        name: "中央汇金投资有限责任公司 / 汇金资管",
        short_name: "中央汇金",
        role: "国家级金融投资平台（平准与长效战略持股）",
        estimated_aum_trillion: 2.45,
        focus: "四大国有行、龙头券商及核心宽基 ETF",
      },
      {
        name: "中国证券金融股份有限公司",
        short_name: "中证金 (CSF)",
        role: "维稳流动性救市主力机构",
        estimated_aum_trillion: 0.65,
        focus: "大盘蓝筹、系统重要性券商及周期龙头",
      },
      {
        name: "全国社会保障基金理事会",
        short_name: "全国社保基金",
        role: "长期战略价值投资标杆",
        estimated_aum_trillion: 0.75,
        focus: "高股息红利、高端制造、医药生物与科技自主可控",
      },
    ],
    industry_allocations: [
      {
        industry: "银行金融",
        weight_pct: 48.5,
        market_value_100m: 18670.0,
        representative_stocks: ["工商银行", "建设银行"],
      },
      {
        industry: "能源周期",
        weight_pct: 16.2,
        market_value_100m: 6237.0,
        representative_stocks: ["中国神华", "中国石油"],
      },
    ],
    top_holdings: [
      {
        code: "601398",
        name: "工商银行",
        holder_name: "中央汇金",
        shareholding_ratio_pct: 34.79,
        market_value_100m: 7850.0,
        industry: "银行金融",
      },
      {
        code: "600900",
        name: "长江电力",
        holder_name: "证金/社保",
        shareholding_ratio_pct: 4.85,
        market_value_100m: 352.0,
        industry: "公用事业",
      },
    ],
  },
  summary: {
    total_shares_100m: 1234.56,
    change_1d_100m: 12.34,
    change_5d_100m: 23.45,
    change_20d_100m: 45.67,
    estimated_net_flow_1d_100m: 8.9,
    estimated_net_flow_5d_100m: 18.9,
    estimated_net_flow_20d_100m: 38.9,
  },
  intraday: {
    minute: {
      date: "2026-10-15",
      times: ["09:31", "09:32"],
      bars: [5.2, 4.8],
      closes: [3200.1, 3205.5],
      table: [
        { code: "510300", name: "沪深300ETF华泰柏瑞", amount: 45.2, pct: 1.25, price: 4.12, volume: 1097000 },
        { code: "510500", name: "中证500ETF", amount: 28.6, pct: 0.85, price: 5.86, volume: 488000 },
      ],
    },
    cum: {
      times: ["09:31", "09:32"],
      today: [5.2, 10.0],
      yesterday: [4.8, 9.2],
      ma20: [4.5, 8.9],
    },
    typical_cases: {
      slots: ["09:31", "09:32"],
      case_amts: [6.5, 12.0],
      norm_amts: [3.2, 5.8],
    },
    volume_signals: {
      support_days: [
        { date: "2024-02-06", amount: 350.5, netflow: 125.8, is_support_day: true },
      ],
      recent_days: [
        { date: "2026-10-15", amount: 180.2, netflow: 45.0, is_support_day: false },
      ],
    },
  },
  indices: indexNames.map((index_name, index) => ({
    index_key: `index-${index}`,
    index_name,
    category: (index_name === "沪深300" || index_name === "上证50") ? "core_broad" : "growth",
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
    mocks.useNationalTeamBacktest.mockImplementation(() => ({
      data: {
        as_of_date: "2026-09-16",
        window_samples: 365,
        sample_days: 60,
        horizons: [
          { days: 5, samples: 55, avg_return_pct: 1.25, median_return_pct: 1.1, win_rate_pct: 61.8, best_return_pct: 4.2, worst_return_pct: -2.1 },
          { days: 20, samples: 40, avg_return_pct: 2.4, median_return_pct: 2.0, win_rate_pct: 57.5, best_return_pct: 8.0, worst_return_pct: -5.0 },
        ],
        by_status: [],
        note: "",
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    }));
    mocks.useNationalTeamIndexSeriesItem.mockImplementation((indexKey: string) => ({
      data: data.indices.find((item) => item.index_key === indexKey),
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    }));
  });

  it("renders proxy disclosure, summary, six independent dual-axis charts, and all ETFs", () => {
    renderPage();

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
    // 每张图只拉自己那条指数序列，不再由页面一次性下载全部 10 条。
    expect(mocks.useNationalTeamIndexSeriesItem).toHaveBeenCalledWith("index-0", 120);
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
    mockIndexSeries(onePointData.indices);

    renderPage();

    const chinextChart = screen.getAllByTestId("national-team-chart")[5];
    expect(chinextChart).toHaveAttribute("data-series-show-symbol", "true,true");
    expect(chinextChart).toHaveAttribute("data-series-symbol-size", "7,7");
    expect(screen.getByText(/当前仅有 1 个份额点/)).toBeInTheDocument();
  });

  it("shows the actual index date and unknown changes instead of a false zero", () => {
    const staleIndices = data.indices.map((item) => ({
      ...item,
      latest_date: "2026-09-15",
      latest_change_1d_100m: null,
      change_5d_100m: null,
      change_20d_100m: null,
    }));
    mocks.useNationalTeamHoldings.mockReturnValue({
      data: {
        ...data,
        indices: staleIndices,
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: mocks.refetch,
    });
    mockIndexSeries(staleIndices);

    renderPage();

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

    const { container } = renderPage();
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
    renderPage();

    expect(mocks.useNationalTeamHoldings).toHaveBeenLastCalledWith(120);
    fireEvent.click(screen.getByRole("radio", { name: "240 天" }));
    expect(mocks.useNationalTeamHoldings).toHaveBeenLastCalledWith(240);

    fireEvent.click(screen.getByRole("button", { name: /刷新/ }));
    expect(mocks.refetch).toHaveBeenCalledTimes(1);
  });

  it("allows switching the rotation ranking timeframe and filtering ETF table by broad-based index", () => {
    renderPage();

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

  it("renders daily flow stacked chart and switches tactical category tabs", () => {
    renderPage();

    expect(screen.getByTestId("national-team-daily-flow-chart")).toBeInTheDocument();
    expect(screen.getByText("全市场宽基每日净申赎走势")).toBeInTheDocument();

    // Default: all 6 charts
    expect(screen.getAllByTestId("national-team-chart")).toHaveLength(6);

    // Switch to "核心大盘" category
    fireEvent.click(screen.getByRole("radio", { name: "核心大盘" }));

    // Only 沪深300 & 上证50 dual-axis charts shown
    expect(screen.getAllByTestId("national-team-chart")).toHaveLength(2);
    expect(screen.getByRole("heading", { name: "沪深300" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "上证50" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "中证500" })).not.toBeInTheDocument();

    // ETF table shows 5 core broad ETFs
    expect(screen.getByText("510300")).toBeInTheDocument();
    expect(screen.getByText("510050")).toBeInTheDocument();
    expect(screen.queryByText("510500")).not.toBeInTheDocument();

    // Switch back to "全部板块"
    fireEvent.click(screen.getByRole("radio", { name: "全部板块" }));
    expect(screen.getAllByTestId("national-team-chart")).toHaveLength(6);
    expect(screen.getByText("510500")).toBeInTheDocument();
  });

  it("renders support score radar, policy milestone timeline, and support zones cost distribution", () => {
    renderPage();

    // 1. Support score radar
    expect(screen.getByTestId("national-team-support-radar")).toBeInTheDocument();
    expect(screen.getByText("国家队托底雷达")).toBeInTheDocument();
    expect(screen.getByText("69")).toBeInTheDocument();
    expect(screen.getByText("积极托底")).toBeInTheDocument();
    expect(screen.getByTestId("national-team-support-confidence")).toHaveTextContent("置信度 86%");
    expect(screen.getByTestId("national-team-score-sparkline")).toHaveTextContent("4 日 +16.5");
    expect(screen.getByTestId("national-team-backtest")).toHaveTextContent("5 日 +1.25% · 胜率 61.8%");
    expect(screen.getByTestId("national-team-backtest")).toHaveTextContent("20 日 +2.40% · 胜率 57.5%");
    expect(screen.getByText(/近60日分位 83%/)).toBeInTheDocument();
    expect(screen.getByText("25.5 / 40")).toBeInTheDocument();

    // 2. Milestones
    expect(screen.getByTestId("national-team-milestones")).toBeInTheDocument();
    expect(screen.getByText("国家队关键政策底救市标尺")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /查看历次救市节点/ }));
    expect(screen.getByText("汇金扩大增持范围并加大力度")).toBeInTheDocument();

    // 3. Support zones
    expect(screen.getByTestId("national-team-support-zones")).toBeInTheDocument();
    expect(screen.getByText("核心指数主力成本中枢与托底点位分布")).toBeInTheDocument();
    expect(screen.getByText(/加权平均买入成本：/)).toBeInTheDocument();
    expect(screen.getByText("3600 点")).toBeInTheDocument();
    expect(screen.getByText("安全垫 +6.94%")).toBeInTheDocument();
    expect(screen.getByText("3400-3600")).toBeInTheDocument();
  });

  it("surfaces low confidence when coverage is poor", () => {
    mocks.useNationalTeamHoldings.mockReturnValue({
      data: {
        ...data,
        support_score: { ...data.support_score, confidence: 0.3 },
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: mocks.refetch,
    });

    renderPage();

    expect(screen.getByTestId("national-team-support-confidence")).toHaveTextContent("置信度 30%");
  });

  it("renders ETF volume and abnormal volume tags", () => {
    renderPage();
    expect(screen.getByText("盘中主力放量异动监测")).toBeInTheDocument();
    expect(screen.getAllByText("成交额").length).toBeGreaterThan(0);
    expect(screen.getAllByText("量比").length).toBeGreaterThan(0);
    expect(screen.getByText("32.5亿")).toBeInTheDocument();
    expect(screen.getAllByText("放量 2.5x").length).toBeGreaterThan(0);
  });

  it("renders estimated net flow from the scalar field without needing ETF points", () => {
    // include_etf_points=false 时 etfs[].points 为空，净申购必须仍能渲染。
    expect(data.etfs.every((item) => item.points.length === 0)).toBe(true);
    renderPage();

    expect(screen.getAllByText("+12.50 亿元").length).toBeGreaterThan(0);
    expect(screen.getAllByText("-2.50 亿元").length).toBeGreaterThan(0);
  });

  it("switches to strategic institutional bottom-holding portrait view", () => {
    renderPage();
    const viewSwitcher = screen.getByTestId("national-team-view-switcher");
    expect(viewSwitcher).toBeInTheDocument();

    const portraitTab = screen.getByText("🏛️ 战略底仓全景");
    fireEvent.click(portraitTab);

    expect(screen.getByTestId("national-team-portrait-panel")).toBeInTheDocument();
    expect(screen.getAllByText("中央汇金").length).toBeGreaterThan(0);
    expect(screen.getByText("中证金 (CSF)")).toBeInTheDocument();
    expect(screen.getByText("全国社保基金")).toBeInTheDocument();
    expect(screen.getByText("国家队战略底仓行业配置与权重分布")).toBeInTheDocument();
    expect(screen.getAllByText("银行金融").length).toBeGreaterThan(0);
    expect(screen.getByText("48.5%")).toBeInTheDocument();
    expect(screen.getByText("核心压舱石标的 · 汇金 / 证金 / 社保前十大战略重仓")).toBeInTheDocument();
    expect(screen.getAllByText("工商银行").length).toBeGreaterThan(0);
    expect(screen.getByText("长江电力")).toBeInTheDocument();

    const exportBtn = screen.getByRole("button", { name: /导出画像 CSV/ });
    expect(exportBtn).toBeInTheDocument();
    fireEvent.click(exportBtn);
  });
});


describe("NationalTeam data quality", () => {  it("shows verified source, business date and fetch time on the date tooltip", async () => {
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
    const { container } = renderPage();
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
    renderPage();
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
    renderPage();

    const exportBtn = screen.getByRole("button", { name: /导出 CSV/ });
    expect(exportBtn).toBeInTheDocument();

    const expandBtns = screen.getAllByRole("button", { name: "放大查看大图" });
    expect(expandBtns.length).toBeGreaterThan(0);
    fireEvent.click(expandBtns[0]);

    expect(screen.getByText(/份额与指数走势大图/)).toBeInTheDocument();
  });

  it("keeps last good data visible and warns when a refetch fails", () => {
    mocks.useNationalTeamHoldings.mockReturnValue({
      data,
      isLoading: false,
      isFetching: false,
      error: new Error("国家队数据加载失败"),
      refetch: mocks.refetch,
    });

    renderPage();

    expect(screen.getByText("数据刷新失败，当前展示上次成功结果")).toBeInTheDocument();
    expect(screen.getByText("国家队数据加载失败")).toBeInTheDocument();
    // 旧数据仍在页面上，不会被错误页整页替掉。
    expect(screen.getByText("1,234.56 亿份")).toBeInTheDocument();
  });

  it("labels the institutional portrait as a static reference with its cut-off date", () => {
    mocks.useNationalTeamHoldings.mockReturnValue({
      data: {
        ...data,
        portrait: {
          ...data.portrait,
          as_of: "2024-12-31",
          source: "上市公司定期报告与公开公告（静态整理，非实时数据）",
          is_static: true,
        },
        summary: { ...data.summary, quality: "partial" as const, coverage_ratio: 0.5 },
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: mocks.refetch,
    });

    renderPage();

    expect(screen.getByText(/部分覆盖/)).toBeInTheDocument();

    fireEvent.click(screen.getByText("🏛️ 战略底仓全景"));
    const reference = screen.getByTestId("national-team-portrait-reference");
    expect(reference).toHaveTextContent("静态参考");
    expect(reference).toHaveTextContent("2024-12-31");
    expect(reference).toHaveTextContent("静态整理");
  });

  it("shows per-index coverage when some members are missing from the latest day", () => {
    const coveredIndices = data.indices.map((item, index) => (
      index === 0
        ? { ...item, coverage_ratio: 0.75, covered_etf_codes: item.etf_codes.slice(0, 3) }
        : item
    ));
    mocks.useNationalTeamHoldings.mockReturnValue({
      data: {
        ...data,
        indices: coveredIndices,
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: mocks.refetch,
    });
    mockIndexSeries(coveredIndices);

    renderPage();

    // 中证1000 本身就有 4 只成员、缺 159629；沪深300 现在是第二个 3/4，
    // 因此按数量断言，避免依赖具体哪张卡片。
    expect(screen.getAllByText("覆盖 3/4 只")).toHaveLength(2);
  });

  it("sorts indices it does not know about to the end instead of the front", () => {
    const unknownIndices = [
      ...data.indices,
      {
        ...data.indices[0],
        index_key: "brand_new",
        index_name: "新宽基指数",
        index_code: "999999.SH",
        etf_codes: [],
        covered_etf_codes: [],
      },
    ];
    mocks.useNationalTeamHoldings.mockReturnValue({
      data: {
        ...data,
        indices: unknownIndices,
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: mocks.refetch,
    });
    mockIndexSeries(unknownIndices);

    const { container } = renderPage();
    const titles = Array.from(container.querySelectorAll(".national-team-index-card__title")).map(
      (node) => node.textContent,
    );
    expect(titles[titles.length - 1]).toBe("新宽基指数");
  });

  describe("NationalTeam sub-tabs and capital flow dashboard", () => {
    beforeEach(() => {
      mocks.useNationalTeamHoldings.mockReturnValue({
        data,
        isLoading: false,
        isFetching: false,
        error: null,
        refetch: mocks.refetch,
      });
    });

    it("defaults to flow tab and renders summary cards, macro chart, and heatmap table", () => {
      renderPage(<NationalTeam />, ["/"]);

      expect(screen.getByTestId("national-team-view-switcher")).toBeInTheDocument();
      expect(screen.getByTestId("national-team-data-status-panel")).toBeInTheDocument();
      expect(screen.getByTestId("national-team-anomaly-banner")).toBeInTheDocument();
      expect(screen.getByText("宽基日度资金流向热力矩阵")).toBeInTheDocument();
      expect(screen.getByTestId("national-team-flow-heatmap-table")).toBeInTheDocument();
      expect(screen.getByTestId("national-team-daily-flow-chart")).toBeInTheDocument();
      expect(screen.getByTestId("national-team-concentration-card")).toBeInTheDocument();
      expect(screen.getByText("CR3 资金集中度")).toBeInTheDocument();
      expect(screen.getByText("样本 ETF 总成交额")).toBeInTheDocument();
      expect(screen.getByText("区间累计净申购")).toBeInTheDocument();
      expect(screen.queryByTestId("national-team-support-radar")).not.toBeInTheDocument();
      expect(screen.queryByTestId("national-team-chart")).not.toBeInTheDocument();

      // Test drilldown modal by clicking a date link in heatmap table
      const dateLinks = screen.getAllByRole("button", { name: "2026-09-16" });
      if (dateLinks.length > 0) {
        fireEvent.click(dateLinks[0]);
        expect(screen.getByText(/2026-09-16 宽基资金流向下钻分析/)).toBeInTheDocument();
        fireEvent.click(screen.getByTestId("drilldown-modal-close"));
      }
    });

    it("switches across sub-tabs: flow -> radar -> etf -> flow", () => {
      renderPage(<NationalTeam />, ["/"]);

      // Switch to Radar tab
      fireEvent.click(screen.getByText("🛡️ 托底信号雷达"));
      expect(screen.getByTestId("national-team-support-radar")).toBeInTheDocument();
      expect(screen.getByTestId("national-team-milestones")).toBeInTheDocument();
      expect(screen.getByTestId("national-team-support-zones")).toBeInTheDocument();
      expect(screen.queryByTestId("national-team-flow-heatmap-table")).not.toBeInTheDocument();

      // Switch to ETF details tab
      fireEvent.click(screen.getByText("📈 宽基与ETF明细"));
      expect(screen.getByText("结构轮动 · 20 日份额变化")).toBeInTheDocument();
      expect(screen.getByTestId("national-team-category-cards")).toBeInTheDocument();
      expect(screen.getByRole("radio", { name: "今日净买入" })).toBeInTheDocument();
      expect(screen.getAllByTestId("national-team-chart").length).toBeGreaterThan(0);
      expect(screen.queryByTestId("national-team-support-radar")).not.toBeInTheDocument();

      // Test preset sort clicking
      fireEvent.click(screen.getByText("今日净买入"));

      // Switch back to Flow Dashboard tab
      fireEvent.click(screen.getByText("📊 资金流向看板"));
      expect(screen.getByTestId("national-team-flow-heatmap-table")).toBeInTheDocument();
      expect(screen.queryByTestId("national-team-support-radar")).not.toBeInTheDocument();
    });

    it("supports switching MacroFlowChart view modes between net flow and turnover", () => {
      renderPage(<NationalTeam />, ["/"]);

      expect(screen.getByText("全市场宽基每日净申赎走势")).toBeInTheDocument();
      expect(screen.getByRole("radio", { name: "净流入与累计走势" })).toBeInTheDocument();

      fireEvent.click(screen.getByRole("radio", { name: "成交额趋势" }));
      expect(screen.getByText("样本 ETF 每日总成交额与基准指数对比")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("radio", { name: "板块细分堆叠" }));
      expect(screen.getByText("各战术板块资金净申购/净赎回估算（亿元）")).toBeInTheDocument();
    });

    it("switches to intraday tab and renders intraday monitor charts and table", () => {
      renderPage(<NationalTeam />, ["/"]);

      // Switch to Intraday tab
      fireEvent.click(screen.getByText("⏱️ 盘中分钟观测"));
      expect(screen.getByTestId("national-team-intraday-minute-chart")).toBeInTheDocument();
      expect(screen.getByTestId("national-team-intraday-cum-chart")).toBeInTheDocument();
      expect(screen.getByTestId("national-team-intraday-typical-chart")).toBeInTheDocument();
      expect(screen.getByTestId("national-team-intraday-signal-chart")).toBeInTheDocument();
      expect(screen.getByText("重点宽基 ETF 分钟成交脉冲与上证走势")).toBeInTheDocument();
      expect(screen.getByText("全天分钟累计成交额进度对比")).toBeInTheDocument();
      expect(screen.getByText("放量护盘日典型分钟特征对照基准")).toBeInTheDocument();
      expect(screen.getByText("20 大重点 ETF 当日成交额排行")).toBeInTheDocument();
      expect(screen.getByText("历史百亿级放量护盘日 vs 近期成交直方对照")).toBeInTheDocument();

      // Test search filter in ETF rank table
      const rankCard = screen.getByTestId("national-team-intraday-rank-card");
      const withinRank = within(rankCard);
      const searchInput = withinRank.getByTestId("intraday-rank-search-input");
      expect(searchInput).toBeInTheDocument();
      fireEvent.change(searchInput, { target: { value: "华泰柏瑞" } });
      expect(withinRank.getByText("沪深300ETF华泰柏瑞")).toBeInTheDocument();
      expect(withinRank.queryByText("中证500ETF")).not.toBeInTheDocument();

      // Clear search to restore all items
      fireEvent.change(searchInput, { target: { value: "" } });
      expect(withinRank.getByText("沪深300ETF华泰柏瑞")).toBeInTheDocument();
      expect(withinRank.getByText("中证500ETF")).toBeInTheDocument();
    });

    it("opens report modal with intraday high-frequency and volume signal insights", () => {
      renderPage(<NationalTeam />, ["/"]);

      // Click "资金简报" button to open modal
      fireEvent.click(screen.getByTestId("national-team-report-btn"));

      // Modal appears
      expect(screen.getByTestId("national-team-poster-content")).toBeInTheDocument();
      expect(screen.getByText("盘中高频与百亿放量护盘信号")).toBeInTheDocument();
      expect(screen.getByText("盘中成交领跑")).toBeInTheDocument();
      expect(screen.getByText("护盘倍数标定")).toBeInTheDocument();

      // Check copy markdown button
      expect(screen.getByTestId("copy-markdown-btn")).toBeInTheDocument();
    });
  });
});
