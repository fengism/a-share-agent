import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HKStockPageContent from "./HKStockPageContent";

const mocks = vi.hoisted(() => ({
  addWatchlist: vi.fn(),
  deleteWatchlist: vi.fn(),
  navigate: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

vi.mock("../../api/queryHooks/hk", () => ({
  useHKStockQuote: (code: string) => ({
    data: {
      code,
      name: "腾讯控股",
      english_name: "TENCENT",
      price: 385.4,
      change: 8.2,
      change_pct: 2.17,
      open: 380.0,
      pre_close: 377.2,
      high: 388.0,
      low: 379.4,
      volume: 18500000,
      amount: 7100000000,
      bid: 385.2,
      ask: 385.4,
      updated_at: "2026-03-30 16:00:00",
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useHKStockHistory: (_code: string, period: string, adjust: string) => ({
    data: {
      items: [
        {
          date: "2026-03-30",
          open: 380.0,
          close: 385.4,
          high: 388.0,
          low: 379.4,
          volume: 18500000,
          amount: 7100000000,
          amplitude: 2.28,
          turnover_pct: 0.2,
          change_pct: 2.17,
        },
      ],
      period,
      adjust,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useHKIndustryComparison: () => ({
    data: {
      code: "00700",
      industry: "资讯科技业",
      sub_industry: "软件服务",
      segment: "数码解决方案服务",
      industry_path: "资讯科技业 - 软件服务 - 数码解决方案服务",
      company_count: 3,
      periods: ["2026中报"],
      current_period: "2026中报",
      peers: [
        { code: "00700", name: "腾讯控股", pe: 22.5, pb: 3.8, net_profit: 45000000000 },
        { code: "09660", name: "地平线机器人-W", pe: null, is_pe_loss: true, pb: 3.37 },
      ],
      all_period_data: {},
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("../../api/queryHooks/watchlist", () => ({
  useWatchlist: () => ({
    data: {
      items: [
        { id: 1, stock_code: "600519", stock_name: "贵州茅台", market: "cn", note: "" },
      ],
    },
    isLoading: false,
  }),
  useAddWatchlistItem: () => ({
    mutateAsync: mocks.addWatchlist,
    isPending: false,
  }),
  useDeleteWatchlistItem: () => ({
    mutateAsync: mocks.deleteWatchlist,
    isPending: false,
  }),
}));

vi.mock("../../charts/IntradayChart", () => ({
  default: ({ viewKey }: { viewKey: string }) => <div data-testid="intraday-chart">{viewKey}</div>,
}));

vi.mock("../../api/queryHooks/stock", () => ({
  useStockIntraday: () => ({
    data: {
      items: [
        { time: "2026-10-02 09:30", price: 385.4, avg_price: 384.0, volume: 1000, amount: 384000, change_pct: 2.17 },
      ],
      prev_close: 377.2,
      source: "腾讯港股分时",
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useStockBusinessIntro: () => ({
    data: {
      code: "00700",
      source: "ths",
      items: {
        主营业务: "公司乃一间投资控股公司。集团主要提供增值服务、营销服务，以及金融科技及企业服务。",
      },
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useRevenueBreakdown: () => ({
    data: {
      code: "00700",
      symbol: "HK0700",
      name: "",
      source: "ths",
      amount_unit: null,
      amount_unit_inferred: false,
      by_product: [],
      by_business: [
        {
          id: null, class_name: "增值服务", is_sub_item: false,
          revenue: null, cost: null, gross_profit: null,
          revenue_share_pct: 48.06, gross_margin_pct: null,
        },
      ],
      by_region: [],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("../../charts/LazyKlineChart", () => ({
  default: ({ viewKey }: { viewKey: string }) => <div data-testid="kline-chart">{viewKey}</div>,
}));

vi.mock("../../charts/IndicatorSubCharts", () => ({
  default: ({ activeType }: { activeType: string }) => (
    <div data-testid="indicator-chart">{activeType}指标图</div>
  ),
}));

describe("HKStockPageContent", () => {
  beforeEach(() => {
    mocks.addWatchlist.mockReset().mockResolvedValue(undefined);
    mocks.deleteWatchlist.mockReset().mockResolvedValue(undefined);
    mocks.navigate.mockReset();
  });

  it("renders HK stock quote details, intraday chart, and switches to kline", () => {
    render(
      <MemoryRouter>
        <HKStockPageContent code="00700" />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "腾讯控股" })).toBeInTheDocument();
    expect(screen.getAllByText("00700")[0]).toBeInTheDocument();
    expect(screen.getByText("HK$385.40")).toBeInTheDocument();
    expect(screen.getByText("+8.20 (+2.17%)")).toBeInTheDocument();
    expect(screen.getByText("港股主板")).toBeInTheDocument();
    expect(screen.getByText("TENCENT")).toBeInTheDocument();
    expect(screen.getByText("T+0 回转交易 · 无单日涨跌幅限制")).toBeInTheDocument();
    expect(screen.getByTestId("intraday-chart")).toBeInTheDocument();

    // Switch to K-line
    fireEvent.click(screen.getByText("K线"));
    expect(screen.getByTestId("kline-chart")).toBeInTheDocument();
  });

  it("adds HK stock to watchlist with market='hk'", async () => {
    render(
      <MemoryRouter>
        <HKStockPageContent code="00700" />
      </MemoryRouter>,
    );

    const watchBtn = screen.getByRole("button", { name: "加入自选" });
    fireEvent.click(watchBtn);

    await waitFor(() => {
      expect(mocks.addWatchlist).toHaveBeenCalledWith({
        stock_code: "00700",
        market: "hk",
        note: "",
      });
    });
  });

  it("does not render link or button to enter HK market overview", () => {
    render(
      <MemoryRouter>
        <HKStockPageContent code="00700" />
      </MemoryRouter>,
    );

    expect(screen.queryByRole("button", { name: "查看H股大盘市场" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "H股市场" })).not.toBeInTheDocument();
    expect(screen.queryByText(/进入.*H股市场/)).not.toBeInTheDocument();
  });

  it("renders the HK main business section like the A-share page", () => {
    render(
      <MemoryRouter>
        <HKStockPageContent code="00700" />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "主营业务" })).toBeInTheDocument();
    expect(
      screen.getByText("公司乃一间投资控股公司。集团主要提供增值服务、营销服务，以及金融科技及企业服务。"),
    ).toBeInTheDocument();
    expect(screen.getByText("来源：THS")).toBeInTheDocument();
    // 交易规则卡与主营业务卡是两件事，不能互相顶替
    expect(screen.getByRole("heading", { name: "港股交易规则" })).toBeInTheDocument();
  });

  it("renders the HK revenue composition with shares only and no amount columns", () => {
    render(
      <MemoryRouter>
        <HKStockPageContent code="00700" />
      </MemoryRouter>,
    );

    // 港股口径：标题/说明必须来自数据源，不能沿用「新浪…毛利构成」
    expect(screen.getByText("同花顺 F10 主营构成分析 · 仅占比，无金额")).toBeInTheDocument();
    expect(screen.queryByText("新浪最新披露口径")).not.toBeInTheDocument();

    // 交互表格与 PDF 表格会各渲染一份，按 testid 收窄避免重复匹配
    const table = within(screen.getByTestId("revenue-breakdown-interactive"));
    expect(table.getByText("增值服务")).toBeInTheDocument();
    expect(table.getByText("48.06%")).toBeInTheDocument();
    // 没有金额就不该摆出三列全是「-」的金额列
    expect(table.queryByText("营业收入")).not.toBeInTheDocument();
    expect(table.queryByText("营业成本")).not.toBeInTheDocument();
    expect(table.queryByText("毛利率")).not.toBeInTheDocument();
  });

  it("switches to MACD, RSI, and KDJ indicator charts", () => {
    render(
      <MemoryRouter>
        <HKStockPageContent code="00700" />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("radio", { name: "MACD" }));
    expect(screen.getByText("MACD 技术指标")).toBeInTheDocument();
    expect(screen.getByTestId("indicator-chart")).toHaveTextContent("macd指标图");

    fireEvent.click(screen.getByRole("radio", { name: "RSI" }));
    expect(screen.getByText("RSI 技术指标")).toBeInTheDocument();
    expect(screen.getByTestId("indicator-chart")).toHaveTextContent("rsi指标图");

    fireEvent.click(screen.getByRole("radio", { name: "KDJ" }));
    expect(screen.getByText("KDJ 技术指标")).toBeInTheDocument();
    expect(screen.getByTestId("indicator-chart")).toHaveTextContent("kdj指标图");
  });

  it("renders the HK industry comparison section with industry path and peers", () => {
    render(
      <MemoryRouter>
        <HKStockPageContent code="00700" />
      </MemoryRouter>,
    );

    expect(screen.getByText("行业地位与同业对比")).toBeInTheDocument();
    expect(screen.getByText("数码解决方案服务")).toBeInTheDocument();
    expect(screen.getByText(/共 3 家公司/)).toBeInTheDocument();
    expect(screen.getByText("地平线机器人-W")).toBeInTheDocument();
  });
});

