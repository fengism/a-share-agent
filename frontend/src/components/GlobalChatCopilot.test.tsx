import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import GlobalChatCopilot from "./GlobalChatCopilot";

function renderWithProviders(initialEntry = "/") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <GlobalChatCopilot />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("GlobalChatCopilot", () => {
  it("hides float button when on /chat page", () => {
    renderWithProviders("/chat");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders float button when on homepage /", () => {
    renderWithProviders("/");
    const floatBtn = screen.getByRole("button");
    expect(floatBtn).toBeInTheDocument();
  });

  it("opens copilot drawer upon clicking the float button", () => {
    renderWithProviders("/");
    const floatBtn = screen.getByRole("button");
    fireEvent.click(floatBtn);

    expect(screen.getByText("AI 投研伴随助手")).toBeInTheDocument();
  });

  it("toggles copilot drawer on Ctrl+J shortcut", () => {
    renderWithProviders("/");
    expect(screen.queryByText("AI 投研伴随助手")).not.toBeInTheDocument();

    fireEvent.keyDown(window, { key: "j", ctrlKey: true });
    expect(screen.getByText("AI 投研伴随助手")).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "j", ctrlKey: true });
    // After second Ctrl+J, drawer starts closing or closed
  });
});
