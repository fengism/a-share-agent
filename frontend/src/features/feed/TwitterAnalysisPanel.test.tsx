import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import TwitterAnalysisPanel from "./TwitterAnalysisPanel";

const mocks = vi.hoisted(() => ({
  regenerate: vi.fn(),
  analyze: vi.fn((username: string) => ({
    data: {
      username,
      content_count: 2,
      sources: [],
      article_count: 2,
      articles: [],
      analysis: `## 核心观点\n${username} 的主要看法`,
      summary: `${username} 的主要看法`,
      stance: "看多",
      confidence: 82,
      core_views: [{
        text: "人工智能产业趋势延续",
        stance: "看多",
        confidence: 85,
        references: [{
          index: 1,
          title: "原始推文",
          url: "https://x.com/source",
          publish_time: "2026-08-08 10:00:00",
        }],
      }],
      sectors: ["人工智能"],
      stocks: ["示例公司"],
      risks: ["估值过高"],
      generated_at: "2026-08-08T10:00:00+00:00",
      cache_hit: true,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  })),
}));

vi.mock("../../api/queries", () => ({
  useMarketTwitterAnalysis: (username: string) => mocks.analyze(username),
  useMarketTwitterAnalysisRefresh: () => ({
    mutate: mocks.regenerate,
    isPending: false,
  }),
}));

describe("TwitterAnalysisPanel", () => {
  it("analyzes the first author and switches between configured authors", async () => {
    render(<TwitterAnalysisPanel authors={["first-author", "second-author"]} />);

    expect(mocks.analyze).toHaveBeenCalledWith("first-author");
    expect(screen.getByText("first-author 的主要看法")).toBeInTheDocument();
    expect(screen.getByText("人工智能产业趋势延续")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /原始推文/ })).toHaveAttribute("href", "https://x.com/source");
    expect(screen.getByText(/缓存结果/)).toBeInTheDocument();

    fireEvent.mouseDown(screen.getByRole("combobox", { name: "选择 Twitter 大 V" }));
    fireEvent.click(await screen.findByText("@second-author"));

    await waitFor(() => expect(mocks.analyze).toHaveBeenLastCalledWith("second-author"));
    expect(screen.getByText("second-author 的主要看法")).toBeInTheDocument();
  });

  it("allows regenerating the selected account analysis", () => {
    render(<TwitterAnalysisPanel authors={["first-author"]} />);

    fireEvent.click(screen.getByRole("button", { name: /重新生成/ }));

    expect(mocks.regenerate).toHaveBeenCalledOnce();
  });

  it("does not request analysis without configured authors", () => {
    render(<TwitterAnalysisPanel authors={[]} />);

    expect(mocks.analyze).toHaveBeenCalledWith("");
    expect(screen.getByText("暂无可解读的 Twitter 账号")).toBeInTheDocument();
  });
});
