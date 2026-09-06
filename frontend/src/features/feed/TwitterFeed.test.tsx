import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { message } from "antd";
import TwitterFeed from "./TwitterFeed";

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

vi.mock("./PaginatedList", () => ({
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

describe("Twitter feed content", () => {
  afterEach(() => vi.clearAllMocks());

  it("renders the Twitter column content and supports manual refresh", () => {
    mocks.refresh.mockImplementation((_variables, options) => options.onSuccess());
    render(
      <MemoryRouter>
        <TwitterFeed searchQuery="" />
      </MemoryRouter>,
    );

    expect(screen.getByText("每 12 小时更新")).toBeInTheDocument();
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
