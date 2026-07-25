import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api/auth", () => ({
  adminResetLinkApi: vi.fn(),
}));

import { adminResetLinkApi } from "../api/auth";
import AdminResetCard from "./AdminResetCard";

const asMock = (fn: unknown) => fn as unknown as ReturnType<typeof vi.fn>;

describe("AdminResetCard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("generates a reset link for the entered username and shows it once", async () => {
    asMock(adminResetLinkApi).mockResolvedValue({
      username: "bob",
      token: "TOK123",
      expires_at: "2026-07-25 10:00:00",
    });
    render(<AdminResetCard />);

    fireEvent.change(screen.getByPlaceholderText("用户名"), { target: { value: "bob" } });
    fireEvent.click(screen.getByRole("button", { name: "生成重置链接" }));

    await waitFor(() =>
      expect(adminResetLinkApi).toHaveBeenCalledWith({ username: "bob", expires_in_hours: 24 }),
    );
    // The one-time link (containing the reset path + token) is rendered.
    expect(await screen.findByText(/reset-password\?token=TOK123/)).toBeInTheDocument();
  });
});
