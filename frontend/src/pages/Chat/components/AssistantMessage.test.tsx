import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AssistantMessage } from "./AssistantMessage";

describe("AssistantMessage", () => {
  it("exposes regeneration for a completed assistant response", () => {
    const onRegenerate = vi.fn();
    render(
      <AssistantMessage
        message={{
          id: "assistant-1",
          role: "assistant",
          content: "回答内容",
          isStreaming: false,
        }}
        onRegenerate={onRegenerate}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "重新生成回答" }));

    expect(onRegenerate).toHaveBeenCalledOnce();
  });

  it("hides regeneration while the response is streaming", () => {
    render(
      <AssistantMessage
        message={{
          id: "assistant-1",
          role: "assistant",
          content: "生成中",
          isStreaming: true,
        }}
        onRegenerate={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: "重新生成回答" })).not.toBeInTheDocument();
  });

  it("turns structured stock results into follow-up actions", () => {
    const onResultAction = vi.fn();
    render(
      <AssistantMessage
        message={{
          id: "assistant-1",
          role: "assistant",
          content: "候选股票：贵州茅台 600519",
          isStreaming: false,
        }}
        onResultAction={onResultAction}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /加入自选/ }));
    expect(onResultAction).toHaveBeenCalledWith("watchlist", expect.objectContaining({ stockCodes: ["600519"] }));
    expect(screen.getByRole("button", { name: /设置提醒/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /转为量化策略/ })).toBeInTheDocument();
  });

  it("supports copying and downloading response as markdown", () => {
    const writeTextSpy = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextSpy,
      },
    });
    window.URL.createObjectURL = vi.fn(() => "blob:mock-url");
    window.URL.revokeObjectURL = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(
      <AssistantMessage
        message={{
          id: "msg-12345678",
          role: "assistant",
          content: "深度研究报告正文",
          isStreaming: false,
        }}
      />,
    );

    // Test copy
    const copyBtn = screen.getByRole("button", { name: "复制回答" });
    fireEvent.click(copyBtn);
    expect(writeTextSpy).toHaveBeenCalledWith("深度研究报告正文");

    // Test download markdown
    const downloadBtn = screen.getByRole("button", { name: "下载 Markdown" });
    fireEvent.click(downloadBtn);
    expect(window.URL.createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();

    // Test export card modal trigger
    const exportCardBtn = screen.getByRole("button", { name: "导出投研长图卡片" });
    expect(exportCardBtn).toBeInTheDocument();
    fireEvent.click(exportCardBtn);
    expect(screen.getByText("导出投研报告卡片")).toBeInTheDocument();
  });

  it("renders next prompt suggestions and handles click", () => {
    const onSelectPrompt = vi.fn();
    render(
      <AssistantMessage
        message={{
          id: "msg-suggestions",
          role: "assistant",
          content: "今日大盘主线题材与涨停连板龙头有哪些？",
          isStreaming: false,
        }}
        onSelectPrompt={onSelectPrompt}
      />,
    );

    expect(screen.getByText(/猜你想问/)).toBeInTheDocument();
    const suggestionBtn = screen.getByText(/分析领涨题材的持续性/);
    fireEvent.click(suggestionBtn);
    expect(onSelectPrompt).toHaveBeenCalledWith(expect.stringContaining("分析领涨题材的持续性"));
  });

  it("renders financial tables with tabular numerals and percentage coloring", () => {
    render(
      <AssistantMessage
        message={{
          id: "msg-table",
          role: "assistant",
          content: "| 股票 | 涨跌幅 |\n| --- | --- |\n| 茅台 | +5.20% |\n| 五粮液 | -1.80% |",
          isStreaming: false,
        }}
      />,
    );

    expect(screen.getByText("+5.20%")).toBeInTheDocument();
    expect(screen.getByText("-1.80%")).toBeInTheDocument();
  });

  it("renders python strategy code block with toolbar badge and copy button", () => {
    render(
      <AssistantMessage
        message={{
          id: "msg-code",
          role: "assistant",
          content: "```python\n# 量化回测策略\ndef handle_data(context):\n    buy(stock, 100)\n```",
          isStreaming: false,
        }}
      />,
    );

    expect(screen.getByText("PYTHON")).toBeInTheDocument();
    expect(screen.getByText("量化策略片段")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "复制代码" })).toBeInTheDocument();
  });
});
