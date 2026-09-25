import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import InviteManagerCard from "./InviteManagerCard";

const mocks = vi.hoisted(() => ({
  refetch: vi.fn(),
  createInvite: vi.fn(),
  revokeInvite: vi.fn(),
  cleanupExpired: vi.fn(),
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
  useInvites: () => ({
    data: [
      {
        code: "INV-VALID-01",
        used: false,
        expired: false,
        created_at: "2026-09-20 10:00:00",
        expires_at: "2026-09-27 10:00:00",
      },
      {
        code: "INV-USED-02",
        used: true,
        expired: false,
        created_at: "2026-09-18 10:00:00",
        expires_at: null,
        used_by: 12,
        used_at: "2026-09-19 11:00:00",
      },
      {
        code: "INV-EXPIRED-03",
        used: false,
        expired: true,
        created_at: "2026-09-10 10:00:00",
        expires_at: "2026-09-11 10:00:00",
      },
    ],
    isLoading: false,
    error: null,
    refetch: mocks.refetch,
  }),
  useCreateInvite: () => ({
    mutate: mocks.createInvite,
    isPending: false,
  }),
  useRevokeInvite: () => ({
    mutate: mocks.revokeInvite,
    isPending: false,
  }),
  useCleanupExpiredInvites: () => ({
    mutate: mocks.cleanupExpired,
    isPending: false,
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
      warning: vi.fn(),
    },
  };
});

describe("InviteManagerCard", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders invite list, metrics bar, and status badges", () => {
    render(<InviteManagerCard />);

    expect(screen.getByText("邀请码管理")).toBeInTheDocument();
    expect(screen.getByText("总邀请码")).toBeInTheDocument();
    expect(screen.getAllByText("有效未使用").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("INV-VALID-01")).toBeInTheDocument();
    expect(screen.getByText("INV-USED-02")).toBeInTheDocument();
    expect(screen.getByText("INV-EXPIRED-03")).toBeInTheDocument();
    expect(screen.getByText("使用者 ID: 12")).toBeInTheDocument();
  });

  it("filters invites by search query", () => {
    render(<InviteManagerCard />);
    const searchInput = screen.getByPlaceholderText("搜索邀请码...");
    fireEvent.change(searchInput, { target: { value: "VALID" } });

    expect(screen.getByText("INV-VALID-01")).toBeInTheDocument();
    expect(screen.queryByText("INV-USED-02")).not.toBeInTheDocument();
  });

  it("triggers create invite mutation on button click", () => {
    render(<InviteManagerCard />);
    const generateBtn = screen.getByRole("button", { name: /生成邀请码/ });
    fireEvent.click(generateBtn);
    expect(mocks.createInvite).toHaveBeenCalled();
  });

  it("triggers refresh when clicking refresh button", () => {
    render(<InviteManagerCard />);
    const refreshBtn = screen.getByRole("button", { name: /刷\s*新/ });
    fireEvent.click(refreshBtn);
    expect(mocks.refetch).toHaveBeenCalled();
  });
});
