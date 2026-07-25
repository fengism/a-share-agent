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
}));

import { loginApi } from "../../api/auth";
import LoginPage from "./index";
import { useAuthStore } from "../../store/authStore";
import { setToken } from "../../api/authToken";

const asMock = (fn: unknown) => fn as unknown as ReturnType<typeof vi.fn>;

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<div>HOME PAGE</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setToken(null);
    useAuthStore.setState({ user: null, bootstrapped: true });
  });

  it("submits trimmed credentials and navigates home on success", async () => {
    asMock(loginApi).mockResolvedValue({ token: "tok", user: { id: 1, username: "alice", is_admin: false, must_change_password: false } });
    renderLogin();

    fireEvent.change(screen.getByPlaceholderText("用户名"), { target: { value: "alice" } });
    fireEvent.change(screen.getByPlaceholderText("密码"), { target: { value: "pw123456" } });
    fireEvent.click(screen.getByRole("button", { name: /登\s*录/ }));

    await waitFor(() =>
      expect(loginApi).toHaveBeenCalledWith({ username: "alice", password: "pw123456" }),
    );
    expect(await screen.findByText("HOME PAGE")).toBeInTheDocument();
  });

  it("shows an error message when login fails", async () => {
    asMock(loginApi).mockRejectedValue(new Error("用户名或密码错误"));
    renderLogin();

    fireEvent.change(screen.getByPlaceholderText("用户名"), { target: { value: "alice" } });
    fireEvent.change(screen.getByPlaceholderText("密码"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /登\s*录/ }));

    expect(await screen.findByText("用户名或密码错误")).toBeInTheDocument();
  });

  it("redirects away when already authenticated", () => {
    useAuthStore.setState({ user: { id: 1, username: "alice", is_admin: false, must_change_password: false }, bootstrapped: true });
    renderLogin();
    expect(screen.getByText("HOME PAGE")).toBeInTheDocument();
  });
});
