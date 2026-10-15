import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MacroFeed from "./MacroFeed";
import type { MacroAnalysis, MacroFeed as MacroFeedData } from "../../types/stock";

const mocks = vi.hoisted(() => ({
  feed: vi.fn(),
  analysis: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useMacroFeed: () => mocks.feed(),
  useMacroAnalysis: () => mocks.analysis(),
}));

const feedData: MacroFeedData = {
  period_start: "2026-09-14",
  period_end: "2026-10-15",
  releases: [
    { id: "r1", title: "2026年9月份居民消费价格同比上涨0.9%", url: "https://stats/r1", published_at: "2026-10-14", source: "国家统计局" },
  ],
  policy_news: [
    { id: "n1", title: "央行新闻发布", url: "https://pbc/n1", published_at: "2026-10-15", source: "中国人民银行" },
  ],
  policy_readings: [
    { id: "p1", title: "政策解读A", url: "https://pbc/p1", published_at: "2026-09-10", source: "中国人民银行" },
  ],
  rates: [
    { key: "lpr1y", label: "LPR 1年期", value: 3.0, unit: "%", period: "2026-09-20", change_bp: -10 },
  ],
  updated_at: "2026-10-15T10:00:00",
  status: "available",
  failed_sources: [],
};

const analysisData: MacroAnalysis = {
  period: "2026-09-14 ~ 2026-10-15",
  summary: "宏观综述内容",
  sentiment: "偏多",
  events: [
    { date: "2026-10-14", category: "物价", title: "CPI上涨", interpretation: "利好消费板块", impact: "偏多", refs: [{ title: "CPI", url: "https://stats/r1" }] },
  ],
  policy_signals: ["稳增长"],
  degraded: false,
  warning: "",
  generated_at: "2026-10-15T10:00:00",
  cached: false,
};

function mockQueries(feed: Partial<MacroFeedData> = {}, analysis: Partial<MacroAnalysis> = {}) {
  mocks.feed.mockReturnValue({
    data: { ...feedData, ...feed },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  });
  mocks.analysis.mockReturnValue({
    data: { ...analysisData, ...analysis },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  });
}

describe("MacroFeed", () => {
  beforeEach(() => {
    mocks.feed.mockReset();
    mocks.analysis.mockReset();
  });

  it("renders the AI summary, event timeline, rates and lists", () => {
    mockQueries();
    render(<MacroFeed />);

    expect(screen.getByText("宏观综述内容")).toBeInTheDocument();
    expect(screen.getByText("稳增长")).toBeInTheDocument();
    expect(screen.getByText("CPI上涨")).toBeInTheDocument();
    expect(screen.getByText("利好消费板块")).toBeInTheDocument();
    expect(screen.getAllByText("偏多").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("LPR 1年期")).toBeInTheDocument();
    expect(screen.getByText("2026年9月份居民消费价格同比上涨0.9%")).toBeInTheDocument();
    expect(screen.getByText("央行新闻发布")).toBeInTheDocument();
  });

  it("switches between policy news and policy readings", () => {
    mockQueries();
    render(<MacroFeed />);

    expect(screen.getByText("央行新闻发布")).toBeInTheDocument();
    expect(screen.queryByText("政策解读A")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("政策解读"));

    expect(screen.getByText("政策解读A")).toBeInTheDocument();
    expect(screen.queryByText("央行新闻发布")).not.toBeInTheDocument();
  });

  it("filters events and lists by the search query", () => {
    mockQueries();
    render(<MacroFeed searchQuery="CPI" />);

    expect(screen.getByText("CPI上涨")).toBeInTheDocument();
    expect(screen.queryByText("央行新闻发布")).not.toBeInTheDocument();
    expect(screen.queryByText("2026年9月份居民消费价格同比上涨0.9%")).not.toBeInTheDocument();
  });

  it("shows the degraded warning when AI is unavailable", () => {
    mockQueries({}, { degraded: true, warning: "AI 解读暂不可用，当前展示原文与确定性汇总。" });
    render(<MacroFeed />);

    expect(screen.getByText("AI 解读暂不可用，当前展示原文与确定性汇总。")).toBeInTheDocument();
  });

  it("caps long lists and expands on demand", () => {
    mockQueries({
      releases: Array.from({ length: 12 }, (_, index) => ({
        id: `r${index}`,
        title: `发布数据${index}`,
        url: `https://stats/${index}`,
        published_at: "2026-10-14",
        source: "国家统计局",
      })),
    });
    render(<MacroFeed />);

    expect(screen.getByText("发布数据0")).toBeInTheDocument();
    expect(screen.queryByText("发布数据11")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("展开全部（12）"));

    expect(screen.getByText("发布数据11")).toBeInTheDocument();
    expect(screen.getByText("收起")).toBeInTheDocument();
  });

  it("shows empty states when there is no macro data", () => {
    mockQueries(
      { releases: [], policy_news: [], policy_readings: [] },
      { events: [], summary: "" },
    );
    render(<MacroFeed />);

    expect(screen.getByText("暂无宏观事件")).toBeInTheDocument();
    expect(screen.getByText("近一个月暂无发布数据")).toBeInTheDocument();
    expect(screen.getByText("暂无金融政策")).toBeInTheDocument();
  });
});
