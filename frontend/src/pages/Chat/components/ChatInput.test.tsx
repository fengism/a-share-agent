import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChatInput } from "./ChatInput";

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("ChatInput", () => {
  it("renders textarea and send button", () => {
    const onChange = vi.fn();
    const onSend = vi.fn();
    const onStop = vi.fn();

    renderWithClient(
      <ChatInput
        value=""
        isStreaming={false}
        onChange={onChange}
        onSend={onSend}
        onStop={onStop}
      />,
    );

    expect(screen.getByPlaceholderText(/输入问题/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /发送/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /\/ 指令/ })).toBeInTheDocument();
  });

  it("triggers onSend when send button is clicked with value", () => {
    const onChange = vi.fn();
    const onSend = vi.fn();
    const onStop = vi.fn();

    renderWithClient(
      <ChatInput
        value="贵州茅台估值"
        isStreaming={false}
        onChange={onChange}
        onSend={onSend}
        onStop={onStop}
      />,
    );

    const sendBtn = screen.getByRole("button", { name: /发送/ });
    expect(sendBtn).not.toBeDisabled();
    fireEvent.click(sendBtn);
    expect(onSend).toHaveBeenCalledOnce();
  });

  it("triggers onStop when streaming", () => {
    const onChange = vi.fn();
    const onSend = vi.fn();
    const onStop = vi.fn();

    renderWithClient(
      <ChatInput
        value="生成中"
        isStreaming={true}
        onChange={onChange}
        onSend={onSend}
        onStop={onStop}
      />,
    );

    const stopBtn = screen.getByRole("button", { name: /停\s*止/ });
    fireEvent.click(stopBtn);
    expect(onStop).toHaveBeenCalledOnce();
  });

  it("handles Enter to send without Shift", () => {
    const onChange = vi.fn();
    const onSend = vi.fn();
    const onStop = vi.fn();

    renderWithClient(
      <ChatInput
        value="测试问题"
        isStreaming={false}
        onChange={onChange}
        onSend={onSend}
        onStop={onStop}
      />,
    );

    const textarea = screen.getByPlaceholderText(/输入问题/);
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });
    expect(onSend).toHaveBeenCalledOnce();
  });
});
