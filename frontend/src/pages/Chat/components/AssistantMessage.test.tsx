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
});
