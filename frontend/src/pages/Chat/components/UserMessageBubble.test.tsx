import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { UserMessageBubble } from "./UserMessageBubble";

describe("UserMessageBubble", () => {
  it("shows the edit affordance only when editing is enabled", () => {
    const { rerender } = render(<UserMessageBubble content="原始问题" />);
    expect(screen.queryByRole("button", { name: /编辑/ })).toBeNull();

    rerender(<UserMessageBubble content="原始问题" disabled onEdit={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /编辑/ })).toBeNull();

    rerender(<UserMessageBubble content="原始问题" onEdit={vi.fn()} />);
    expect(screen.getByRole("button", { name: /编辑/ })).toBeInTheDocument();
  });

  it("submits the edited content and trims whitespace", () => {
    const onEdit = vi.fn();
    render(<UserMessageBubble content="原始问题" onEdit={onEdit} />);

    fireEvent.click(screen.getByRole("button", { name: /编辑/ }));
    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(textarea.value).toBe("原始问题");
    fireEvent.change(textarea, { target: { value: "  改后的问题  " } });
    fireEvent.click(screen.getByRole("button", { name: /重新生成/ }));

    expect(onEdit).toHaveBeenCalledOnce();
    expect(onEdit).toHaveBeenCalledWith("改后的问题");
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("supports Enter to submit and Shift+Enter for newline, and cancel restores", () => {
    const onEdit = vi.fn();
    render(<UserMessageBubble content="原始问题" onEdit={onEdit} />);

    fireEvent.click(screen.getByRole("button", { name: /编辑/ }));
    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "回车提交" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });
    expect(onEdit).toHaveBeenCalledWith("回车提交");

    fireEvent.click(screen.getByRole("button", { name: /编辑/ }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "不会被保留" } });
    fireEvent.click(screen.getByRole("button", { name: /取\s*消/ }));
    expect(onEdit).toHaveBeenCalledOnce();
    expect(screen.getByText("原始问题")).toBeInTheDocument();
  });

  it("keeps the confirm button disabled for blank drafts", () => {
    const onEdit = vi.fn();
    render(<UserMessageBubble content="原始问题" onEdit={onEdit} />);

    fireEvent.click(screen.getByRole("button", { name: /编辑/ }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "   " } });
    expect(screen.getByRole("button", { name: /重新生成/ })).toBeDisabled();
    expect(onEdit).not.toHaveBeenCalled();
  });
});
