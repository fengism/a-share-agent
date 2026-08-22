import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AppUserMenu from "./AppUserMenu";

const user = {
  id: 1,
  username: "admin-user",
  is_admin: true,
  must_change_password: false,
};

describe("AppUserMenu", () => {
  it("shows identity and routes menu actions through existing callbacks", async () => {
    const onLogout = vi.fn().mockResolvedValue(undefined);
    const onSettings = vi.fn();
    render(
      <AppUserMenu
        user={user}
        isMobile={false}
        onSettings={onSettings}
        onLogout={onLogout}
      />,
    );

    const trigger = screen.getByRole("button", { name: "用户菜单" });
    expect(trigger).toHaveTextContent("admin-user");
    fireEvent.click(trigger);
    expect(screen.getByText("管理员")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("menuitem", { name: "设置" }));
    expect(onSettings).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();

    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole("menuitem", { name: "退出登录" }));
    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  it("keeps the mobile trigger compact but accessible", () => {
    render(
      <AppUserMenu
        user={{ ...user, is_admin: false }}
        isMobile
        onSettings={vi.fn()}
        onLogout={vi.fn()}
      />,
    );

    const trigger = screen.getByRole("button", { name: "用户菜单" });
    expect(trigger).not.toHaveTextContent("admin-user");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });
});
