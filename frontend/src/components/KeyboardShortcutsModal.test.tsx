import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import KeyboardShortcutsModal from "./KeyboardShortcutsModal";

describe("KeyboardShortcutsModal", () => {
  it("renders trigger button and opens modal when clicked", () => {
    render(<KeyboardShortcutsModal />);
    const button = screen.getByRole("button", { name: "打开键盘快捷键指南" });
    expect(button).toBeInTheDocument();

    fireEvent.click(button);
    expect(screen.getByText("键盘快捷键指南")).toBeInTheDocument();
    expect(screen.getByText("快速打开股票/指标搜索")).toBeInTheDocument();
  });

  it("toggles modal when pressing '?' key outside of input fields", () => {
    render(<KeyboardShortcutsModal />);
    expect(screen.queryByText("键盘快捷键指南")).toBeNull();

    fireEvent.keyDown(window, { key: "?" });
    expect(screen.getByText("键盘快捷键指南")).toBeInTheDocument();
  });

  it("does not toggle modal when pressing '?' inside an input field", () => {
    render(
      <div>
        <input data-testid="test-input" />
        <KeyboardShortcutsModal />
      </div>,
    );

    const input = screen.getByTestId("test-input");
    input.focus();

    fireEvent.keyDown(input, { key: "?" });
    expect(screen.queryByText("键盘快捷键指南")).toBeNull();
  });
});
