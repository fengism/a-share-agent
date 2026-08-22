import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { message } from "antd";
import Twitter from ".";

const mocks = vi.hoisted(() => ({
  refresh: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useMarketTwitterFeed: () => ({
    data: [{ title: "市场观察", author: "market-author" }],
    dataUpdatedAt: Date.now(),
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useMarketTwitterFeedRefresh: () => ({
    mutate: mocks.refresh,
    isPending: false,
  }),
  useMarketTwitterAnalysis: () => ({
    data: {
      username: "market-author",
      content_count: 3,
      sources: [],
      article_count: 3,
      articles: [],
      analysis: "## 核心观点\n长期看多科技创新。",
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useMarketTwitterAnalysisRefresh: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}));

vi.mock("../../features/feed/PaginatedList", () => ({
  default: ({ items }: { items: Array<{ title: string }> }) => <div>资讯数量：{items.length}</div>,
}));

vi.mock("antd", async () => {
  const actual = await vi.importActual<typeof import("antd")>("antd");
  return {
    ...actual,
    message: {
      ...actual.message,
      error: vi.fn(),
      success: vi.fn(),
    },
  };
});

describe("Twitter page", () => {
  afterEach(() => vi.clearAllMocks());

  it("renders as a standalone feed and supports manual refresh", () => {
    mocks.refresh.mockImplementation((_variables, options) => options.onSuccess());
    render(
      <MemoryRouter>
        <Twitter />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Twitter 财经动态" })).toBeInTheDocument();
    expect(screen.getAllByText(/每 12 小时自动/).length).toBeGreaterThan(0);
    expect(screen.getByText("资讯数量：1")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /AI 大 V 解读/ })).toBeInTheDocument();
    expect(screen.getByText("长期看多科技创新。")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /立即刷新/ }));

    expect(mocks.refresh).toHaveBeenCalledWith(undefined, expect.objectContaining({
      onSuccess: expect.any(Function),
      onError: expect.any(Function),
    }));
    expect(message.success).toHaveBeenCalledWith("Twitter 资讯已刷新");
  });
});
