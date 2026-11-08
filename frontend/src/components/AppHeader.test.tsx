import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import AppHeader from "./AppHeader";

vi.mock("../store/authStore", () => ({
  useAuthStore: (selector: (state: { user: null; logout: () => Promise<void> }) => unknown) => selector({ user: null, logout: vi.fn() }),
}));
vi.mock("../styles/ui", async () => {
  const actual = await vi.importActual<typeof import("../styles/ui")>("../styles/ui");
  return {
    ...actual,
    useColors: () => ({ border: "#234", textPrimary: "#fff" }),
    useTokens: () => ({ space: ["0", "4px", "8px", "12px", "16px", "20px"], z: { header: "20" } }),
  };
});
vi.mock("./DeferredAppHeaderSearch", () => ({ default: () => <div>全局股票搜索</div> }));
vi.mock("./ThemeSelector", () => ({ default: () => <button>主题</button> }));
vi.mock("./KeyboardShortcutsModal", () => ({ default: () => <button>快捷键</button> }));
vi.mock("./AppUserMenu", () => ({ default: () => null }));
vi.mock("./GlobalTaskIndicator", () => ({ default: () => null }));
vi.mock("./HeaderMarketTicker", () => ({ default: () => null }));

describe("AppHeader command bar", () => {
  it("keeps search and theme controls without duplicating sidebar navigation", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppHeader isMobile={false} themeKey="stellar-blue" onMobileNavOpen={vi.fn()} />
      </MemoryRouter>,
    );

    expect(screen.getByText("全局股票搜索")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AI 投研助手" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "主题" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "全局快捷操作" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /策略/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /数据源/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /推送通知/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^分析$/ })).not.toBeInTheDocument();
  });

  it("navigates to /chat when AI Assistant launcher is clicked", () => {
    let currentPath = "";
    function PathTracker() {
      const location = useLocation();
      currentPath = location.pathname;
      return null;
    }

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AppHeader isMobile={false} themeKey="stellar-blue" onMobileNavOpen={vi.fn()} />
        <PathTracker />
      </MemoryRouter>,
    );

    const aiTrigger = screen.getByRole("button", { name: "AI 投研助手" });
    expect(aiTrigger).toBeInTheDocument();
    fireEvent.click(aiTrigger);
    expect(currentPath).toBe("/chat");
  });

  it("hides desktop keyboard shortcuts on mobile viewports", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppHeader isMobile={true} themeKey="stellar-blue" onMobileNavOpen={vi.fn()} />
      </MemoryRouter>,
    );

    expect(screen.queryByRole("button", { name: "快捷键" })).not.toBeInTheDocument();
  });
});
