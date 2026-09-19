import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const mutationMocks = vi.hoisted(() => ({
  mutate: vi.fn(),
}));

vi.mock("../../api/queryHooks/system", () => ({
  useVersionCheck: vi.fn(),
  useUpdateStatus: vi.fn(),
  useTriggerUpdate: vi.fn(() => ({ mutate: mutationMocks.mutate, isPending: false })),
}));

vi.mock("../../store/authStore", () => ({
  useAuthStore: vi.fn((selector: (s: { user: unknown }) => unknown) =>
    selector({ user: mockState.user }),
  ),
}));

import { useUpdateStatus, useVersionCheck } from "../../api/queryHooks/system";
import SystemUpdateCard from "./SystemUpdateCard";

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

describe("SystemUpdateCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mutationMocks.mutate.mockReset();
    mockState.user = { id: 1, username: "admin", is_admin: true };
    asMock(useUpdateStatus).mockReturnValue({ data: { status: "idle" } });
  });

  it("renders the system update card with current version and check button", () => {
    mockVersion({
      current_version: "v1.2.0",
      latest_version: "v1.2.0",
      update_available: false,
    });

    render(<SystemUpdateCard />);

    expect(screen.getByText("系统版本与更新")).toBeInTheDocument();
    expect(screen.getByText("v1.2.0")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /检查更新/ })).toBeInTheDocument();
  });

  it("shows up-to-date message after clicking check update when no update is available", async () => {
    mockVersion({
      current_version: "v1.2.0",
      latest_version: "v1.2.0",
      update_available: false,
    });

    render(<SystemUpdateCard />);
    fireEvent.click(screen.getByRole("button", { name: /检查更新/ }));

    expect(await screen.findByText("当前已是最新版本，无需更新。")).toBeInTheDocument();
  });

  it("shows update available alert and allows admin to trigger update", () => {
    mockVersion({
      current_version: "v1.2.0",
      latest_version: "v1.3.0",
      update_available: true,
    });

    render(<SystemUpdateCard />);

    expect(screen.getByText("发现新版本：")).toBeInTheDocument();
    expect(screen.getByText("v1.3.0")).toBeInTheDocument();
    const updateButton = screen.getByRole("button", { name: /立即在线更新/ });
    expect(updateButton).toBeInTheDocument();

    fireEvent.click(updateButton);
    expect(mutationMocks.mutate).toHaveBeenCalledTimes(1);
  });

  it("shows contact admin message for non-admin users when update is available", () => {
    mockState.user = { id: 2, username: "user", is_admin: false };
    mockVersion({
      current_version: "v1.2.0",
      latest_version: "v1.3.0",
      update_available: true,
    });

    render(<SystemUpdateCard />);

    expect(screen.getByText("当前账号为非管理员，如需更新请联系系统管理员操作。")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /立即在线更新/ })).not.toBeInTheDocument();
  });
});
