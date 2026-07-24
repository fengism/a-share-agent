import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api/auth", () => ({
  changePasswordApi: vi.fn(),
}));

import { changePasswordApi } from "../api/auth";
import ChangePasswordCard from "./ChangePasswordCard";

const asMock = (fn: unknown) => fn as unknown as ReturnType<typeof vi.fn>;

describe("ChangePasswordCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("submits the old and new password", async () => {
    asMock(changePasswordApi).mockResolvedValue({ ok: true, revoked_sessions: 1 });
    render(<ChangePasswordCard />);

    fireEvent.change(screen.getByLabelText("当前密码"), { target: { value: "pw123456" } });
    fireEvent.change(screen.getByLabelText("新密码"), { target: { value: "newpw12345" } });
    fireEvent.change(screen.getByLabelText("确认新密码"), { target: { value: "newpw12345" } });
    fireEvent.click(screen.getByRole("button", { name: "修改密码" }));

    await waitFor(() =>
      expect(changePasswordApi).toHaveBeenCalledWith({
        old_password: "pw123456",
        new_password: "newpw12345",
      }),
    );
  });

  it("blocks submission when the confirmation does not match", async () => {
    render(<ChangePasswordCard />);

    fireEvent.change(screen.getByLabelText("当前密码"), { target: { value: "pw123456" } });
    fireEvent.change(screen.getByLabelText("新密码"), { target: { value: "newpw12345" } });
    fireEvent.change(screen.getByLabelText("确认新密码"), { target: { value: "different" } });
    fireEvent.click(screen.getByRole("button", { name: "修改密码" }));

    expect(await screen.findByText("两次输入的新密码不一致")).toBeInTheDocument();
    expect(changePasswordApi).not.toHaveBeenCalled();
  });
});
