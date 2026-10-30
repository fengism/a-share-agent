import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AppLayout from "./AppLayout";

vi.mock("../hooks/useMediaQuery", () => ({ useMediaQuery: () => false }));
vi.mock("../styles/ui", () => ({
  useColors: () => ({ pageBg: "#000" }),
  useThemeStore: (selector: (state: { themeKey: "stellar-blue" }) => unknown) => selector({ themeKey: "stellar-blue" }),
}));
vi.mock("./AppHeader", () => ({ default: () => <header>顶部栏</header> }));
vi.mock("./AppSidebar", () => ({
  default: ({
    activeKey,
    collapsed,
    onCollapse,
  }: {
    activeKey: string;
    collapsed?: boolean;
    onCollapse?: (collapsed: boolean) => void;
  }) => (
    <aside data-active-key={activeKey} data-collapsed={collapsed ? "true" : "false"}>
      侧边栏
      <button data-testid="sidebar-toggle-btn" onClick={() => onCollapse?.(!collapsed)}>
        切换折叠
      </button>
    </aside>
  ),
}));
vi.mock("./GlobalChatCopilot", () => ({ default: () => null }));
vi.mock("./ChatSessionSyncBridge", () => ({ default: () => null }));
vi.mock("./WorkflowRuntimeBridge", () => ({ default: () => null }));
vi.mock("./UpdateBanner", () => ({ default: () => null }));

describe("AppLayout", () => {
  beforeEach(() => {
    vi.stubGlobal("scrollTo", vi.fn());
    localStorage.clear();
  });

  it("keeps global navigation and moves focus to content after route changes", async () => {
    render(
      <MemoryRouter initialEntries={["/first"]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/first" element={<Link to="/second">下一页</Link>} />
            <Route path="/second" element={<div>第二页内容</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "跳到主要内容" })).toHaveAttribute("href", "#main-content");
    fireEvent.click(screen.getByRole("link", { name: "下一页" }));

    await screen.findByText("第二页内容");
    await waitFor(() => expect(screen.getByRole("main")).toHaveFocus());
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: "auto" });
    expect(screen.getByText("侧边栏")).toBeInTheDocument();
    expect(screen.getByText("顶部栏")).toBeInTheDocument();
  });

  it("keeps the industry classification route under its own navigation item", () => {
    render(
      <MemoryRouter initialEntries={["/industry-classification"]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/industry-classification" element={<div>行业基础数据</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("侧边栏")).toHaveAttribute("data-active-key", "/master-data");
  });

  it("keeps the stock profile under the stock navigation item", () => {
    render(
      <MemoryRouter initialEntries={["/stock/600519"]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/stock/:code" element={<div>个股资料</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("侧边栏")).toHaveAttribute("data-active-key", "/analysis");
  });

  it("maps the Hong Kong market route to the market navigation item", () => {
    render(
      <MemoryRouter initialEntries={["/hk-market"]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/hk-market" element={<div>港股市场</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("侧边栏")).toHaveAttribute("data-active-key", "/market");
  });

  it("persists collapsed state to localStorage when toggled", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<div>首页内容</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    const sidebar = screen.getByText("侧边栏");
    expect(sidebar).toHaveAttribute("data-collapsed", "false");

    fireEvent.click(screen.getByTestId("sidebar-toggle-btn"));
    expect(sidebar).toHaveAttribute("data-collapsed", "true");
    expect(localStorage.getItem("trade_agent_sidebar_collapsed")).toBe("true");

    fireEvent.click(screen.getByTestId("sidebar-toggle-btn"));
    expect(sidebar).toHaveAttribute("data-collapsed", "false");
    expect(localStorage.getItem("trade_agent_sidebar_collapsed")).toBe("false");
  });

  it("initializes collapsed state from localStorage", () => {
    localStorage.setItem("trade_agent_sidebar_collapsed", "true");

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<div>首页内容</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("侧边栏")).toHaveAttribute("data-collapsed", "true");
  });

  it("toggles collapsed state using keyboard shortcut Cmd+B / Ctrl+B", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<div>首页内容</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    const sidebar = screen.getByText("侧边栏");
    expect(sidebar).toHaveAttribute("data-collapsed", "false");

    // Press Cmd+B
    fireEvent.keyDown(window, { key: "b", metaKey: true });
    expect(sidebar).toHaveAttribute("data-collapsed", "true");
    expect(localStorage.getItem("trade_agent_sidebar_collapsed")).toBe("true");

    // Press Ctrl+B
    fireEvent.keyDown(window, { key: "B", ctrlKey: true });
    expect(sidebar).toHaveAttribute("data-collapsed", "false");
    expect(localStorage.getItem("trade_agent_sidebar_collapsed")).toBe("false");
  });
});
