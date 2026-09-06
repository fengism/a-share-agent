import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mutationMocks = vi.hoisted(() => ({
  mutate: vi.fn(),
}));

vi.mock("../api/queryHooks/system", () => ({
  useVersionCheck: vi.fn(),
  useTriggerUpdate: vi.fn(() => ({ mutate: mutationMocks.mutate, isPending: false })),
}));

vi.mock("../store/authStore", () => ({
  useAuthStore: vi.fn((selector: (s: { user: unknown }) => unknown) =>
    selector({ user: mockState.user }),
  ),
}));

import { useVersionCheck } from "../api/queryHooks/system";
import UpdateBanner from "./UpdateBanner";

const asMock = (fn: unknown) => fn as unknown as ReturnType<typeof vi.fn>;

const mockState = { user: null as unknown };

function mockVersion(data: {
  current_version: string;
  latest_version: string | null;
  update_available: boolean;
}) {
  asMock(useVersionCheck).mockReturnValue({ data, refetch: vi.fn() });
}

describe("UpdateBanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockState.user = { id: 1, username: "admin", is_admin: true };
  });

  it("renders nothing when no update is available", () => {
    mockVersion({
      current_version: "abc1234",
      latest_version: "abc1234",
      update_available: false,
    });
    const { container } = render(<UpdateBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows versions and update button for admin", () => {
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
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
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
