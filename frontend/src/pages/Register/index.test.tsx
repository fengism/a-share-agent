import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../api/auth", () => ({
  loginApi: vi.fn(),
  registerApi: vi.fn(),
  logoutApi: vi.fn(),
  meApi: vi.fn(),
  needsSetupApi: vi.fn(),
  createInviteApi: vi.fn(),
  listInvitesApi: vi.fn(),
}));

import { needsSetupApi } from "../../api/auth";
import RegisterPage from "./index";
import { useAuthStore } from "../../store/authStore";
import { setToken } from "../../api/authToken";

const asMock = (fn: unknown) => fn as unknown as ReturnType<typeof vi.fn>;

function renderRegister() {
  return render(
    <MemoryRouter initialEntries={["/register"]}>
      <RegisterPage />
    </MemoryRouter>,
  );
}

describe("RegisterPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setToken(null);
    useAuthStore.setState({ user: null, bootstrapped: true });
  });

  it("first-user setup mode hides the invite field and labels the admin action", async () => {
    asMock(needsSetupApi).mockResolvedValue({ needs_setup: true });
    renderRegister();

    expect(await screen.findByText("首位注册用户将成为管理员")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("管理员提供的邀请码")).toBeNull();
    expect(screen.getByRole("button", { name: "创建管理员账号" })).toBeInTheDocument();
  });

  it("invite mode requires an invite code", async () => {
    asMock(needsSetupApi).mockResolvedValue({ needs_setup: false });
    renderRegister();

    expect(await screen.findByPlaceholderText("管理员提供的邀请码")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /注\s*册/ })).toBeInTheDocument();
  });
});
