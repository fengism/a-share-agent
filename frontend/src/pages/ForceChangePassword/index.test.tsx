import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

vi.mock("../../api/auth", () => ({
  loginApi: vi.fn(),
  registerApi: vi.fn(),
  logoutApi: vi.fn(),
  meApi: vi.fn(),
  needsSetupApi: vi.fn(),
  createInviteApi: vi.fn(),
  listInvitesApi: vi.fn(),
  changePasswordApi: vi.fn(),
}));

import { changePasswordApi, meApi } from "../../api/auth";
import ForceChangePasswordPage from "./index";
import { useAuthStore } from "../../store/authStore";
import { setToken } from "../../api/authToken";

const asMock = (fn: unknown) => fn as unknown as ReturnType<typeof vi.fn>;

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/force-change-password"]}>
      <Routes>
        <Route path="/force-change-password" element={<ForceChangePasswordPage />} />
        <Route path="/" element={<div>HOME PAGE</div>} />
        <Route path="/login" element={<div>LOGIN PAGE</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ForceChangePasswordPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setToken("tok");
    useAuthStore.setState({
      user: { id: 1, username: "admin", is_admin: true, must_change_password: true },
      bootstrapped: true,
    });
  });

  it("changes the password then continues into the app", async () => {
    asMock(changePasswordApi).mockResolvedValue({ ok: true });
    asMock(meApi).mockResolvedValue({ id: 1, username: "admin", is_admin: true, must_change_password: false });
    renderPage();

    fireEvent.change(screen.getByLabelText("当前密码（临时密码）"), { target: { value: "temp-pw" } });
    fireEvent.change(screen.getByLabelText("新密码"), { target: { value: "newpass1" } });
    fireEvent.change(screen.getByLabelText("确认新密码"), { target: { value: "newpass1" } });
    fireEvent.click(screen.getByRole("button", { name: "修改并继续" }));

    await waitFor(() =>
      expect(changePasswordApi).toHaveBeenCalledWith({ old_password: "temp-pw", new_password: "newpass1" }),
    );
    expect(await screen.findByText("HOME PAGE")).toBeInTheDocument();
  });

  it("redirects into the app when a change is not required", () => {
    useAuthStore.setState({
      user: { id: 1, username: "admin", is_admin: true, must_change_password: false },
      bootstrapped: true,
    });
    renderPage();
    expect(screen.getByText("HOME PAGE")).toBeInTheDocument();
  });
});
