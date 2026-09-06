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
  default: ({ activeKey }: { activeKey: string }) => (
    <aside data-active-key={activeKey}>侧边栏</aside>
  ),
}));
vi.mock("./ChatSessionSyncBridge", () => ({ default: () => null }));
vi.mock("./WorkflowRuntimeBridge", () => ({ default: () => null }));

describe("AppLayout", () => {
  beforeEach(() => {
    vi.stubGlobal("scrollTo", vi.fn());
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
});
