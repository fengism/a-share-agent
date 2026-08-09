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
});
