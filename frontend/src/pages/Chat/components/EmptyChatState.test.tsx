import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EmptyChatState } from "./EmptyChatState";

describe("EmptyChatState", () => {
  it("renders empty state header and prompt cards", () => {
    const onSelectPrompt = vi.fn();
    render(<EmptyChatState onSelectPrompt={onSelectPrompt} />);

    expect(screen.getByText("AI 智能投研与选股工作台")).toBeInTheDocument();
    expect(screen.getByText("低估值高股息白马")).toBeInTheDocument();
    expect(screen.getByText("主力资金与主线题材")).toBeInTheDocument();
  });

  it("calls onSelectPrompt when a prompt card is clicked", () => {
    const onSelectPrompt = vi.fn();
    render(<EmptyChatState onSelectPrompt={onSelectPrompt} />);

    const card = screen.getByText("低估值高股息白马");
    fireEvent.click(card);

    expect(onSelectPrompt).toHaveBeenCalledWith(
      expect.stringContaining("帮我找PE小于20"),
    );
  });

  it("filters prompts when category is switched", () => {
    const onSelectPrompt = vi.fn();
    render(<EmptyChatState onSelectPrompt={onSelectPrompt} />);

    const screenerTab = screen.getByText("策略选股");
    fireEvent.click(screenerTab);

    expect(screen.getByText("低估值高股息白马")).toBeInTheDocument();
    expect(screen.queryByText("先进封装与芯片产业链")).not.toBeInTheDocument();
  });
});
