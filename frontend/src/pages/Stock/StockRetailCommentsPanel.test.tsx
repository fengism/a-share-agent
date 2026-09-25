import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import StockRetailCommentsPanel from "./StockRetailCommentsPanel";

const mocks = vi.hoisted(() => ({ query: vi.fn(), retry: vi.fn() }));
vi.mock("../../api/queries", () => ({ useRetailSentiment: (...args: unknown[]) => mocks.query(...args) }));
const data = {
  score: 65, guba_post_count: 1, post_count: 1, bullish_ratio: 0.6,
  summary: "讨论情绪偏积极",
  sample_posts: [{ text: "看好后续表现", author: "投资者", publish_time: "10:00" }],
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.query.mockReturnValue({ data, isLoading: false, error: null, refetch: mocks.retry });
});

describe("StockRetailCommentsPanel", () => {
  it("preserves stats, summary and semantic sample lists on the stock profile", () => {
    render(<StockRetailCommentsPanel code="600519" />);
    expect(mocks.query).toHaveBeenCalledWith("600519");
    expect(screen.getByText("散户评论（1条）")).toBeVisible();
    expect(screen.getByText("60.0%")).toBeVisible();
    expect(screen.getByText("讨论情绪偏积极")).toBeVisible();
    expect(screen.getAllByRole("list")).toHaveLength(1);
    expect(screen.getByRole("listitem")).toHaveTextContent("看好后续表现投资者 | 10:00");
  });

  it("shows loading without misleading empty stats", () => {
    mocks.query.mockReturnValue({ isLoading: true });
    render(<StockRetailCommentsPanel code="600519" />);
    expect(screen.getByLabelText("数据加载中")).toBeInTheDocument();
    expect(screen.queryByText("情绪评分")).not.toBeInTheDocument();
  });

  it("supports failed requests and retry", () => {
    mocks.query.mockReturnValue({ error: new Error("请求失败"), refetch: mocks.retry });
    render(<StockRetailCommentsPanel code="600519" />);
    expect(screen.getByText("散户评论加载失败")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /重\s*试/ }));
    expect(mocks.retry).toHaveBeenCalledOnce();
  });

  it("shows missing samples without inventing a score", () => {
    mocks.query.mockReturnValue({ data: { ...data, score: null, bullish_ratio: null, summary: "暂无样本", sample_posts: [] } });
    render(<StockRetailCommentsPanel code="600519" />);
    expect(screen.getByText("暂无散户讨论样本")).toBeVisible();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    expect(screen.queryByText("60.0%")).not.toBeInTheDocument();
  });
});
