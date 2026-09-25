import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import StockPage from ".";

const mocks = vi.hoisted(() => ({
  add: vi.fn(),
  remove: vi.fn(),
  stockInfo: vi.fn(),
  financialSection: vi.fn(),
  informationTabs: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useAnalysisSnapshot: () => ({ data: { cached_analysis: null }, isLoading: false, error: null, refetch: vi.fn() }),
  useStockInfo: (code: string) => {
    mocks.stockInfo(code);
    return ({
    data: {
      code: "600519",
      name: "贵州茅台",
      listing_date: "2001-08-27",
      total_shares: 1_256_197_800,
      circulating_shares: 1_256_197_800,
      pe_ttm: 22.35,
      pe_static: 23.18,
      pb: 7.8,
      market_cap: 1_900_000_000_000,
      float_market_cap: 1_880_000_000_000,
      turnover_pct: 0.42,
      exchange_industry: "白酒",
      first_industry: { code: "BK0477", name: "酿酒行业" },
      second_industry: { code: "BK0896", name: "白酒" },
      current_price: 1512.5,
      concepts: [{ code: "GN172", name: "核心资产" }],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    });
  },
  useStockBusinessIntro: () => ({
    data: {
      code: "600519",
      source: "ths",
      items: { 主营业务: "茅台酒及系列酒的生产与销售", 产品类型: "酒类" },
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useWatchlist: () => ({ data: { items: [] }, isLoading: false }),
  useAddWatchlistItem: () => ({ mutateAsync: mocks.add, isPending: false }),
  useDeleteWatchlistItem: () => ({ mutateAsync: mocks.remove, isPending: false }),
  useKlineData: () => ({ data: { items: [] }, isLoading: false, error: null, refetch: vi.fn(), isFetching: false }),
  useStockIntraday: () => ({ data: { items: [], prev_close: 1500 }, isLoading: false, error: null, refetch: vi.fn() }),
  useStockChipDistribution: () => ({
    data: { code: "600519", peak_price: 1498.8 },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useCategorizedStockNews: () => ({ data: { positive: [], negative: [], neutral: [] }, isLoading: false, error: null, refetch: vi.fn() }),
  useStockBulletins: () => ({ data: { items: [], page: 1, total_pages: 0 }, isLoading: false, error: null, refetch: vi.fn() }),
  useStockReports: () => ({ data: { items: [] }, isLoading: false, error: null, refetch: vi.fn() }),
  useStockFundFlow: () => ({ data: [], isLoading: false, error: null, refetch: vi.fn() }),
}));

vi.mock("../../charts/LazyKlineChart", () => ({ default: () => <div>K 线图</div> }));
vi.mock("../../charts/IntradayChart", () => ({ default: () => <div>分时图</div> }));
vi.mock("../../charts/IndicatorSubCharts", () => ({
  default: ({ activeType }: { activeType?: string }) => (
    <div>{activeType ? activeType.toUpperCase() : "MACD"} 指标图</div>
  ),
}));
vi.mock("../../features/stock-insights/AnnouncementsPanel", () => ({
  default: () => {
    mocks.informationTabs();
    return <div>公告面板</div>;
  },
}));
vi.mock("../../features/stock-insights/ResearchReportsPanel", () => ({ default: () => <div>研报面板</div> }));
vi.mock("../../features/stock-insights/FundFlowPanel", () => ({ default: () => <div>资金面板</div> }));
vi.mock("../../features/stock-insights/ChipDistributionPanel", () => ({
  default: () => <div>筹码分布内容</div>,
}));
vi.mock("./HKStockPageContent", () => ({
  default: ({ code }: { code: string }) => <div data-testid="hk-stock-page">港股资料页: {code}</div>,
}));
vi.mock("../../features/investment-research/KeyFinancialMetricsSection", () => ({
  default: () => {
    mocks.financialSection();
    return <div>最近四个报告期财务指标</div>;
  },
}));

vi.mock("../../features/investment-research/RevenueBreakdownSection", () => ({
  default: () => <div>营收与毛利构成</div>,
}));

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}{location.search}{location.hash}</span>;
}

describe("StockPage", () => {
  const originalIntersectionObserver = globalThis.IntersectionObserver;

  beforeEach(() => {
    mocks.add.mockReset().mockResolvedValue(undefined);
    mocks.remove.mockReset().mockResolvedValue(undefined);
    mocks.stockInfo.mockReset();
    mocks.financialSection.mockReset();
    mocks.informationTabs.mockReset();
    globalThis.IntersectionObserver = originalIntersectionObserver;
  });

  afterEach(() => {
    globalThis.IntersectionObserver = originalIntersectionObserver;
  });

  it("renders stock facts and opens the independent analysis route", async () => {
    render(
      <MemoryRouter initialEntries={["/stock/600519"]}>
        <Routes>
          <Route path="/stock/:code" element={<StockPage />} />
          <Route path="/analysis/:code" element={<div>分析页</div>} />
        </Routes>
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "贵州茅台" })).toBeInTheDocument();
    expect(screen.getByText("600519")).toBeInTheDocument();
    expect(screen.getByText("¥1512.50")).toBeInTheDocument();
    expect(screen.getByText("总市值")).toBeInTheDocument();
    expect(screen.getByText("1.90万亿")).toBeInTheDocument();
    expect(screen.getByText("茅台酒及系列酒的生产与销售")).toBeInTheDocument();
    expect(screen.getByText("公司概览")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "关键指标" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "主营业务" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "行情、技术与筹码" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "财务指标" })).toBeInTheDocument();
    expect(screen.getByText("最近四个报告期财务指标")).toBeInTheDocument();
    expect(screen.getByText("营收与毛利构成")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "财务" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByRole("heading", { name: "资讯与研究" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "资讯" }));
    expect(screen.getByRole("heading", { name: "资讯与研究" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "散户评论" })).toBeInTheDocument();

    expect(screen.getByRole("link", { name: "个股资料" })).toHaveAttribute("aria-current", "page");
    fireEvent.click(screen.getByRole("button", { name: "进入 AI 分析" }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/analysis/600519"));
  });

  it("shows MACD and chip distribution with the market charts", async () => {
    render(
      <MemoryRouter initialEntries={["/stock/600519"]}>
        <Routes><Route path="/stock/:code" element={<StockPage />} /></Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByText("MACD"));
    expect(screen.getByText("MACD 指标图")).toBeInTheDocument();

    fireEvent.click(screen.getByText("RSI"));
    expect(screen.getByText("RSI 指标图")).toBeInTheDocument();

    fireEvent.click(screen.getByText("KDJ"));
    expect(screen.getByText("KDJ 指标图")).toBeInTheDocument();

    fireEvent.click(screen.getByText("筹码分布"));
    expect(await screen.findByText("筹码分布内容")).toBeInTheDocument();
  });

  it("adds the stock to the watchlist", async () => {
    render(
      <MemoryRouter initialEntries={["/stock/600519"]}>
        <Routes><Route path="/stock/:code" element={<StockPage />} /></Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "加入自选" }));
    await waitFor(() => expect(mocks.add).toHaveBeenCalledWith({ stock_code: "600519", note: "" }));
  });

  it("rejects invalid route codes before starting stock requests", () => {
    render(
      <MemoryRouter initialEntries={["/stock/abc600519xyz"]}>
        <Routes><Route path="/stock/:code" element={<StockPage />} /></Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("股票代码无效")).toBeInTheDocument();
    expect(mocks.stockInfo).not.toHaveBeenCalled();
  });

  it("redirects supported prefixed codes to their canonical profile URL", async () => {
    render(
      <MemoryRouter initialEntries={["/stock/SH600519"]}>
        <Routes><Route path="/stock/:code" element={<StockPage />} /></Routes>
        <LocationProbe />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/stock/600519"));
    expect(mocks.stockInfo).toHaveBeenCalledWith("600519");
  });

  it("keeps profile tab and anchor when normalizing a stock code", async () => {
    const scroll = vi.fn();
    const originalScroll = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = scroll;
    const { unmount } = render(
      <MemoryRouter initialEntries={["/stock/SH600519?tab=information#stock-details"]}>
        <Routes><Route path="/stock/:code" element={<StockPage />} /></Routes>
        <LocationProbe />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/stock/600519?tab=information#stock-details"));
    expect(screen.getByRole("tab", { name: "资讯" })).toHaveAttribute("aria-selected", "true");
    await waitFor(() => expect(scroll).toHaveBeenCalledWith({ block: "start" }));
    unmount();
    HTMLElement.prototype.scrollIntoView = originalScroll;
  });

  it("renders HK stock content when given an HK stock code", () => {
    render(
      <MemoryRouter initialEntries={["/stock/00700"]}>
        <Routes><Route path="/stock/:code" element={<StockPage />} /></Routes>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("hk-stock-page")).toHaveTextContent("港股资料页: 00700");
    expect(mocks.stockInfo).not.toHaveBeenCalled();
  });

  it("redirects short HK stock code to canonical 5-digit profile URL", async () => {
    render(
      <MemoryRouter initialEntries={["/stock/700"]}>
        <Routes><Route path="/stock/:code" element={<StockPage />} /></Routes>
        <LocationProbe />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/stock/00700"));
  });

  it("defers financial and information requests until their sections approach the viewport", async () => {
    const observers: IntersectionObserverCallback[] = [];
    globalThis.IntersectionObserver = class {
      readonly root = null;
      readonly rootMargin = "300px 0px";
      readonly thresholds = [0];
      constructor(callback: IntersectionObserverCallback) {
        observers.push(callback);
      }
      disconnect() {}
      observe() {}
      takeRecords() { return []; }
      unobserve() {}
    };

    render(
      <MemoryRouter initialEntries={["/stock/600519"]}>
        <Routes><Route path="/stock/:code" element={<StockPage />} /></Routes>
      </MemoryRouter>,
    );

    expect(mocks.financialSection).not.toHaveBeenCalled();
    expect(mocks.informationTabs).not.toHaveBeenCalled();
    expect(screen.getByLabelText("财务、估值、资金与资讯即将加载")).toBeInTheDocument();

    await act(async () => {
      observers.forEach((notify) => {
        notify([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver);
      });
      await Promise.resolve();
    });

    expect(mocks.financialSection).toHaveBeenCalledTimes(1);
    expect(mocks.informationTabs).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("tab", { name: "资讯" }));
    expect(mocks.informationTabs).toHaveBeenCalledTimes(1);
  });
});
