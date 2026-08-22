import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PushModal from "./PushModal";

describe("PushModal", () => {
  it("uses report-oriented labels and resets the form after success", async () => {
    const onConfirm = vi.fn().mockResolvedValue(true);
    render(
      <PushModal
        open
        type="analysis"
        code="600519"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByText("推送报告")).toBeInTheDocument();
    expect(screen.getByRole("radiogroup", { name: "推送目标" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "飞书" }));
    fireEvent.change(screen.getByRole("textbox", { name: "接收人" }), { target: { value: "ou_receiver" } });

    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /推送/ }));

    await waitFor(() => expect(onConfirm).toHaveBeenCalledWith({
      target: "feishu",
      type: "analysis",
      date: undefined,
      code: "600519",
      feishu_receiver: "ou_receiver",
    }));
    await waitFor(() => expect(screen.getByRole("radio", { name: "Notion" })).toBeChecked());
    expect(screen.queryByRole("textbox", { name: "接收人" })).not.toBeInTheDocument();
  });

  it("keeps receiver input after a failed push", async () => {
    const onConfirm = vi.fn().mockResolvedValue(false);
    render(
      <PushModal
        open
        type="daily_review"
        date="2026-08-13"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("radio", { name: "飞书" }));
    const receiverInput = screen.getByRole("textbox", { name: "接收人" });
    fireEvent.change(receiverInput, { target: { value: "oc_group" } });
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /推送/ }));

    await waitFor(() => expect(onConfirm).toHaveBeenCalledOnce());
    expect(receiverInput).toHaveValue("oc_group");
    expect(screen.getByRole("radio", { name: "飞书" })).toBeChecked();
  });

  it("ignores repeated confirmations while a push is in flight", async () => {
    let resolvePush!: (value: boolean) => void;
    const onConfirm = vi.fn().mockImplementation(() => new Promise<boolean>((resolve) => {
      resolvePush = resolve;
    }));
    render(
      <PushModal
        open
        type="analysis"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );

    const confirmButton = within(screen.getByRole("dialog")).getByRole("button", { name: /推送/ });
    act(() => {
      fireEvent.click(confirmButton);
      fireEvent.click(confirmButton);
    });

    expect(onConfirm).toHaveBeenCalledOnce();
    await act(async () => {
      resolvePush(true);
    });
  });
});
