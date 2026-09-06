import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import PriceAnomalyTab from "./PriceAnomalyTab";

const mocks = vi.hoisted(() => ({
  detailRefetch: vi.fn(),
  countRefetch: vi.fn(),
  useMarketPriceAnomaly: vi.fn(),
  useMarketPriceAnomalyCount: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useMarketPriceAnomaly: mocks.useMarketPriceAnomaly,
  useMarketPriceAnomalyCount: mocks.useMarketPriceAnomalyCount,
}));

vi.mock("../../styles/ui", () => ({
  useColors: () => ({
    up: "#f5222d",
    down: "#52c41a",
    textPrimary: "#1f2329",
    textSecondary: "#646a73",
    textMuted: "#8f959e",
    warning: "#f79009",
  }),
  useTokens: () => ({ weight: { semibold: 600 } }),
}));

function renderTab() {
  return render(
    <MemoryRouter>
      <PriceAnomalyTab />
    </MemoryRouter>,
  );
}

describe("PriceAnomalyTab", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-01T02:00:00Z"));
    mocks.detailRefetch.mockReset();
    mocks.countRefetch.mockReset();
    mocks.useMarketPriceAnomaly.mockReset().mockReturnValue({
      data: {
        source: "东方财富",
        date: "20260901",
        is_stale: false,
        fetched_at: "2026-09-01T10:30:00+08:00",
        page_no: 1,
        page_size: 200,
        pages: 1,
        items: [
          {
            code: "688001",
            name: "科创样本",
            market: "SH",
            change_pct: 10.5,
            deviation: 151.2,
            days: 10,
            board: 6,
            rule_code: 40,
            rule: "连续十个交易日内日收盘价涨跌幅偏离值累计达到+150%",
            is_today: true,
          },
          {
            code: "920001",
            name: "北交样本",
            market: "BJ",
            change_pct: -3,
            deviation: -12,
            days: 10,
            board: 8,
            rule_code: 8,
            rule: "北交所连续10个交易日内3次出现同向异常波动",
            is_today: false,
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: mocks.detailRefetch,
    });
    mocks.useMarketPriceAnomalyCount.mockReset().mockReturnValue({
      data: {
        source: "东方财富",
        date: "2026-09-01",
        is_stale: false,
        fetched_at: "2026-09-01T10:30:00+08:00",
        page_no: 1,
        page_size: 50,
        pages: 1,
        items: [
          {
            code: "600000",
            name: "浦发银行",
            market: "SH",
            price: 10.23,
            change_pct: 1.2,
            times: 4,
            deviation: 12.5,
            days: 10,
            board: 1,
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: mocks.countRefetch,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders exchange anomaly details and tightened STAR Market rules", () => {
    renderTab();

    expect(screen.getByText("数据日期：2026-09-01")).toBeInTheDocument();
    expect(screen.getByText("科创样本")).toBeInTheDocument();
    expect(screen.getByText("北交样本")).toBeInTheDocument();
    expect(screen.getByText("北交所")).toBeInTheDocument();
    expect(screen.getByText("连续十个交易日内日收盘价涨跌幅偏离值累计达到+150%")).toBeInTheDocument();
    expect(screen.getByText("今日异动")).toBeInTheDocument();
    expect(screen.getByText("窗口记录")).toBeInTheDocument();
    expect(mocks.useMarketPriceAnomaly).toHaveBeenCalledWith(1, 200, true);
    expect(mocks.useMarketPriceAnomalyCount).toHaveBeenCalledWith(1, 50, "", "", false);
  });

  it("switches to the aggregated anomaly count view", () => {
    renderTab();

    fireEvent.click(screen.getByText("异动统计"));

    expect(screen.getByText("浦发银行")).toBeInTheDocument();
    expect(screen.getByText("10.23")).toBeInTheDocument();
    expect(screen.getByText("4次")).toBeInTheDocument();
    expect(screen.getByText("本页异动次数")).toBeInTheDocument();
    expect(mocks.useMarketPriceAnomaly).toHaveBeenLastCalledWith(1, 200, false);
    expect(mocks.useMarketPriceAnomalyCount).toHaveBeenLastCalledWith(1, 50, "", "", true);
  });

  it("labels fallback records against their data date instead of today", () => {
    mocks.useMarketPriceAnomaly.mockReturnValue({
      data: {
        source: "东方财富",
        date: "2026-08-31",
        fetched_at: "2026-08-31T15:30:00+08:00",
        page_no: 1,
        page_size: 200,
        pages: 1,
        is_stale: true,
        items: [
          {
            code: "688001",
            name: "科创样本",
            market: "SH",
            change_pct: 10.5,
            deviation: 151.2,
            days: 10,
            board: 6,
            rule_code: 40,
            rule: "连续十个交易日内日收盘价涨跌幅偏离值累计达到+150%",
            is_today: true,
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: mocks.detailRefetch,
    });

    renderTab();

    expect(screen.getByText("数据日异动")).toBeInTheDocument();
    expect(screen.getByText("数据日触发")).toBeInTheDocument();
    expect(screen.getByText("已回退至最近数据日")).toBeInTheDocument();
  });
});
