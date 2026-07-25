import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

vi.mock("../../api/auth", () => ({
  resetPasswordApi: vi.fn(),
}));

import { resetPasswordApi } from "../../api/auth";
import ResetPasswordPage from "./index";

const asMock = (fn: unknown) => fn as unknown as ReturnType<typeof vi.fn>;

function renderAt(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/login" element={<div>LOGIN</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ResetPasswordPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("submits the token from the URL with the new password", async () => {
    asMock(resetPasswordApi).mockResolvedValue({ ok: true });
    renderAt("/reset-password?token=abc123");

    fireEvent.change(screen.getByLabelText("新密码"), { target: { value: "newpass1" } });
    fireEvent.change(screen.getByLabelText("确认新密码"), { target: { value: "newpass1" } });
    fireEvent.click(screen.getByRole("button", { name: "重置密码" }));

    await waitFor(() =>
      expect(resetPasswordApi).toHaveBeenCalledWith({ token: "abc123", new_password: "newpass1" }),
    );
    expect(await screen.findByText("密码已重置")).toBeInTheDocument();
  });

  it("warns and disables submit when the token is missing", () => {
    renderAt("/reset-password");
    expect(screen.getByText("链接无效：缺少重置令牌")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重置密码" })).toBeDisabled();
  });
});
