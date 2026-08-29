import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PushModal from "./PushModal";

describe("PushModal", () => {
  it("defaults reports to Feishu and resets the form after success", async () => {
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
    expect(screen.getByText("使用系统默认接收人")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "接收人" }), { target: { value: "  ou_receiver  " } });
    expect(screen.getByText("使用自定义用户接收人")).toBeInTheDocument();

    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /推送到飞书/ }));

    await waitFor(() => expect(onConfirm).toHaveBeenCalledWith({
      target: "feishu",
      type: "analysis",
      date: undefined,
      code: "600519",
      feishu_receiver: "ou_receiver",
    }));
    await waitFor(() => expect(screen.getByText("使用系统默认接收人")).toBeInTheDocument());
    expect(screen.getByRole("textbox", { name: "接收人" })).toHaveValue("");
  });

  it("blocks malformed Feishu receiver IDs before submitting", () => {
    const onConfirm = vi.fn();
    render(
      <PushModal
        open
        type="analysis"
        code="600519"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByRole("textbox", { name: "接收人" }), { target: { value: "invalid" } });

    expect(screen.getByText("接收人 ID 必须以 oc_ 或 ou_ 开头")).toBeInTheDocument();
    expect(within(screen.getByRole("dialog")).getByRole("button", { name: /推送/ })).toBeDisabled();
    expect(onConfirm).not.toHaveBeenCalled();
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

    const receiverInput = screen.getByRole("textbox", { name: "接收人" });
    fireEvent.change(receiverInput, { target: { value: "oc_group" } });
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /推送/ }));

    await waitFor(() => expect(onConfirm).toHaveBeenCalledOnce());
    expect(receiverInput).toHaveValue("oc_group");
    expect(screen.getByRole("radio", { name: /飞书/ })).toBeChecked();
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

  it("switches to Notion without submitting a Feishu receiver", async () => {
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

    fireEvent.click(screen.getByText("Notion"));
    expect(screen.queryByRole("textbox", { name: "接收人" })).not.toBeInTheDocument();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /转存到 Notion/ }));

    await waitFor(() => expect(onConfirm).toHaveBeenCalledWith({
      target: "notion",
      type: "analysis",
      date: undefined,
      code: "600519",
      feishu_receiver: "",
    }));
  });
});
