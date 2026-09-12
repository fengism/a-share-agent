import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";

const mutationMocks = vi.hoisted(() => ({
  mutate: vi.fn(),
}));

vi.mock("../api/queryHooks/system", () => ({
  useVersionCheck: vi.fn(),
  useUpdateStatus: vi.fn(),
  useTriggerUpdate: vi.fn(() => ({ mutate: mutationMocks.mutate, isPending: false })),
}));

vi.mock("../store/authStore", () => ({
  useAuthStore: vi.fn((selector: (s: { user: unknown }) => unknown) =>
    selector({ user: mockState.user }),
  ),
}));

import { useUpdateStatus, useVersionCheck } from "../api/queryHooks/system";
import UpdateBanner from "./UpdateBanner";

const asMock = (fn: unknown) => fn as unknown as ReturnType<typeof vi.fn>;

const mockState = { user: null as unknown };

function mockVersion(data: {
  current_version: string;
  latest_version: string | null;
  update_available: boolean;
}) {
  asMock(useVersionCheck).mockReturnValue({
    data,
    refetch: vi.fn().mockResolvedValue({}),
    isFetching: false,
  });
}

describe("UpdateBanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mutationMocks.mutate.mockReset();
    mockState.user = { id: 1, username: "admin", is_admin: true };
    asMock(useUpdateStatus).mockReturnValue({ data: { status: "idle" } });
  });

  it("shows the idle manual-check bar when no update is available", () => {
    mockVersion({
      current_version: "abc1234",
      latest_version: "abc1234",
      update_available: false,
    });
    render(<UpdateBanner />);
    expect(screen.getByText(/当前版本 abc1234/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /检查更新/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /立即更新/ })).not.toBeInTheDocument();
  });

  it("shows the complete semantic version without truncating it", () => {
    mockVersion({
      current_version: "v1.12.345",
      latest_version: "abc1234ffff",
      update_available: false,
    });
    render(<UpdateBanner />);
    expect(screen.getByText("当前版本 v1.12.345")).toBeInTheDocument();
  });

  it("shows a friendly development label to admins instead of the raw dev version", () => {
    mockVersion({
      current_version: "dev",
      latest_version: "def5678",
      update_available: false,
    });
    render(<UpdateBanner />);
    expect(screen.getByText("开发环境")).toBeInTheDocument();
    expect(screen.queryByText(/当前版本 dev/)).not.toBeInTheDocument();
  });

  it("hides the development version from non-admin users", () => {
    mockState.user = { id: 2, username: "bob", is_admin: false };
    mockVersion({
      current_version: "dev",
      latest_version: "def5678",
      update_available: false,
    });
    render(<UpdateBanner />);
    expect(screen.queryByText(/dev/i)).not.toBeInTheDocument();
    expect(screen.queryByText("开发环境")).not.toBeInTheDocument();
  });

  it("explains to admins that development builds cannot update online", async () => {
    mockVersion({
      current_version: "dev",
      latest_version: "def5678",
      update_available: false,
    });
    render(<UpdateBanner />);
    fireEvent.click(screen.getByRole("button", { name: /检查更新/ }));
    expect(await screen.findByText("开发环境不支持在线更新")).toBeInTheDocument();
    expect(screen.queryByText("已是最新版本")).not.toBeInTheDocument();
  });

  it("does not expose development-build details to non-admin users", async () => {
    mockState.user = { id: 2, username: "bob", is_admin: false };
    mockVersion({
      current_version: "dev",
      latest_version: "def5678",
      update_available: false,
    });
    render(<UpdateBanner />);
    fireEvent.click(screen.getByRole("button", { name: /检查更新/ }));
    expect(await screen.findByText("版本信息不可用")).toBeInTheDocument();
    expect(screen.queryByText("已是最新版本")).not.toBeInTheDocument();
  });

  it("shows versions and update button for admin when update is available", () => {
    mockVersion({
      current_version: "abc1234",
      latest_version: "def5678",
      update_available: true,
    });
    render(<UpdateBanner />);
    expect(screen.getByText(/def5678/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /立即更新/ })).toBeInTheDocument();
  });

  it("hides the update button for non-admin users", () => {
    mockState.user = { id: 2, username: "bob", is_admin: false };
    mockVersion({
      current_version: "abc1234",
      latest_version: "def5678",
      update_available: true,
    });
    render(<UpdateBanner />);
    expect(screen.getByText(/请联系管理员更新/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /立即更新/ })).not.toBeInTheDocument();
  });

  it("reports a successful manual check only after refetch completes", async () => {
    let resolveRefetch!: (value: { error: null }) => void;
    const refetch = vi.fn(() => new Promise<{ error: null }>((resolve) => {
      resolveRefetch = resolve;
    }));
    asMock(useVersionCheck).mockReturnValue({
      data: {
        current_version: "abc1234",
        latest_version: "def5678",
        update_available: false,
      },
      refetch,
      isFetching: false,
    });
    render(<UpdateBanner />);
    fireEvent.click(screen.getByRole("button", { name: /检查更新/ }));

    expect(refetch).toHaveBeenCalled();
    expect(screen.queryByText("已是最新版本")).not.toBeInTheDocument();

    await act(async () => resolveRefetch({ error: null }));
    expect(await screen.findByText("已是最新版本")).toBeInTheDocument();
  });

  it("shows an error when the manual version check fails", async () => {
    const refetch = vi.fn().mockResolvedValue({ error: new Error("网络异常") });
    asMock(useVersionCheck).mockReturnValue({
      data: {
        current_version: "abc1234",
        latest_version: "abc1234",
        update_available: false,
      },
      refetch,
      isFetching: false,
    });
    render(<UpdateBanner />);
    fireEvent.click(screen.getByRole("button", { name: /检查更新/ }));

    expect(await screen.findByText("检查更新失败：网络异常")).toBeInTheDocument();
    expect(screen.queryByText("已是最新版本")).not.toBeInTheDocument();
  });

  it("shows updater failures and allows retry", async () => {
    mockVersion({
      current_version: "abc1234",
      latest_version: "def5678",
      update_available: true,
    });
    asMock(useUpdateStatus).mockReturnValue({
      data: { status: "failed", message: "镜像拉取失败" },
    });
    mutationMocks.mutate.mockImplementation((_value, options) => options.onSuccess());

    render(<UpdateBanner />);
    fireEvent.click(screen.getByRole("button", { name: /立即更新/ }));

    expect(await screen.findByText("镜像拉取失败")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /立即更新/ })).toBeInTheDocument();
  });

  it("reports when a failed update was rolled back", async () => {
    mockVersion({
      current_version: "abc1234",
      latest_version: "def5678",
      update_available: true,
    });
    asMock(useUpdateStatus).mockReturnValue({
      data: { status: "failed_rolled_back", message: "更新失败，已自动恢复旧版本" },
    });
    mutationMocks.mutate.mockImplementation((_value, options) => options.onSuccess());

    render(<UpdateBanner />);
    fireEvent.click(screen.getByRole("button", { name: /立即更新/ }));

    expect(await screen.findByText("更新失败，已自动恢复旧版本")).toBeInTheDocument();
  });

  it("reports a high-severity rollback failure", async () => {
    mockVersion({
      current_version: "abc1234",
      latest_version: "def5678",
      update_available: true,
    });
    asMock(useUpdateStatus).mockReturnValue({
      data: { status: "failed_rollback_failed", message: "自动回滚失败，请立即人工恢复" },
    });
    mutationMocks.mutate.mockImplementation((_value, options) => options.onSuccess());

    render(<UpdateBanner />);
    fireEvent.click(screen.getByRole("button", { name: /立即更新/ }));

    expect(await screen.findByText("自动回滚失败，请立即人工恢复")).toBeInTheDocument();
  });

  it("triggers the update mutation on click", async () => {
    mockVersion({
      current_version: "abc1234",
      latest_version: "def5678",
      update_available: true,
    });
    render(<UpdateBanner />);
    fireEvent.click(screen.getByRole("button", { name: /立即更新/ }));
    await waitFor(() => expect(mutationMocks.mutate).toHaveBeenCalled());
  });
});
