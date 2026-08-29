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
vi.mock("./AppSidebar", () => ({ default: () => <aside>侧边栏</aside> }));
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
});
