import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import UserManagerCard from "./UserManagerCard";
import { useAuthStore } from "../../store/authStore";

const mocks = vi.hoisted(() => ({
  refetch: vi.fn(),
  updateStatus: vi.fn(),
  updateRole: vi.fn(),
  deleteUser: vi.fn(),
  revokeSessions: vi.fn(),
  updateMustChange: vi.fn(),
  adminResetLink: vi.fn().mockResolvedValue({
    token: "mock_token_123",
    username: "normal_user",
    expires_at: "2026-09-23 12:00:00",
  }),
}));

vi.mock("../../api/auth", () => ({
  adminResetLinkApi: mocks.adminResetLink,
}));

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQueryClient: () => ({
      invalidateQueries: vi.fn(),
    }),
  };
});

vi.mock("../../api/queries", () => ({
  useAdminUsers: () => ({
    data: [
      {
        id: 1,
        username: "admin_user",
        is_admin: true,
        is_active: true,
        must_change_password: false,
        created_at: "2026-09-01 12:00:00",
      },
      {
        id: 2,
        username: "normal_user",
        is_admin: false,
        is_active: true,
        must_change_password: true,
        created_at: "2026-09-02 12:00:00",
      },
      {
        id: 3,
        username: "disabled_user",
        is_admin: false,
        is_active: false,
        must_change_password: false,
        created_at: "2026-09-03 12:00:00",
      },
    ],
    isLoading: false,
    error: null,
    refetch: mocks.refetch,
  }),
  useUpdateUserStatus: () => ({
    mutate: mocks.updateStatus,
  }),
  useUpdateUserRole: () => ({
    mutate: mocks.updateRole,
  }),
  useDeleteUser: () => ({
    mutate: mocks.deleteUser,
  }),
  useRevokeUserSessions: () => ({
    mutate: mocks.revokeSessions,
  }),
  useUpdateUserMustChangePassword: () => ({
    mutate: mocks.updateMustChange,
  }),
}));

vi.mock("antd", async () => {
  const actual = await vi.importActual<typeof import("antd")>("antd");
  return {
    ...actual,
    message: {
      ...actual.message,
      error: vi.fn(),
      success: vi.fn(),
    },
  };
});

describe("UserManagerCard", () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: { id: 1, username: "admin_user", is_admin: true, must_change_password: false },
      bootstrapped: true,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders user table, statistics, and marks current logged-in account", () => {
    render(<UserManagerCard />);

    expect(screen.getByText("用户管理")).toBeInTheDocument();
    expect(screen.getByText("总用户数")).toBeInTheDocument();
    expect(screen.getByText("正常运行")).toBeInTheDocument();
    expect(screen.getByText("admin_user")).toBeInTheDocument();
    expect(screen.getByText("当前账号")).toBeInTheDocument();
    expect(screen.getByText("normal_user")).toBeInTheDocument();
    expect(screen.getByText("disabled_user")).toBeInTheDocument();
    expect(screen.getAllByText("已禁用").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("待改密")).toBeInTheDocument();
  });

  it("filters users when searching by username", () => {
    render(<UserManagerCard />);
    const searchInput = screen.getByPlaceholderText("按用户名搜索");
    fireEvent.change(searchInput, { target: { value: "normal" } });

    expect(screen.getByText("normal_user")).toBeInTheDocument();
    expect(screen.queryByText("disabled_user")).not.toBeInTheDocument();
  });

  it("triggers refresh when clicking refresh button", () => {
    render(<UserManagerCard />);
    fireEvent.click(screen.getByRole("button", { name: /刷\s*新/ }));
    expect(mocks.refetch).toHaveBeenCalled();
  });

  it("triggers revoke sessions on click", () => {
    render(<UserManagerCard />);
    const disconnectButtons = screen.getAllByRole("button").filter((btn) =>
      btn.querySelector(".anticon-disconnect"),
    );
    expect(disconnectButtons.length).toBeGreaterThan(0);
    fireEvent.click(disconnectButtons[1]); // for normal_user
    expect(mocks.revokeSessions).toHaveBeenCalledWith(2, expect.any(Object));
  });

  it("opens reset password modal and generates link", async () => {
    render(<UserManagerCard />);
    const keyButtons = screen.getAllByRole("button").filter((btn) =>
      btn.querySelector(".anticon-key"),
    );
    expect(keyButtons.length).toBeGreaterThan(0);
    fireEvent.click(keyButtons[1]); // for normal_user

    expect(await screen.findByText("生成重置链接 — normal_user")).toBeInTheDocument();
    const generateBtn = screen.getByRole("button", { name: "生成重置链接" });
    fireEvent.click(generateBtn);

    await waitFor(() => {
      expect(mocks.adminResetLink).toHaveBeenCalledWith({
        username: "normal_user",
        expires_in_hours: 24,
      });
    });
    expect(await screen.findByText("重置链接已生成")).toBeInTheDocument();
  });

  it("triggers toggle must change password on click", () => {
    render(<UserManagerCard />);
    // normal_user currently has must_change_password=true, so its button shows "取消改密"
    const cancelMcButton = screen.getByRole("button", { name: "取消改密" });
    fireEvent.click(cancelMcButton);
    expect(mocks.updateMustChange).toHaveBeenCalledWith(
      { userId: 2, mustChangePassword: false },
      expect.any(Object),
    );
  });
});
