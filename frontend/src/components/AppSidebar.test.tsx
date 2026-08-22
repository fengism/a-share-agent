import type { PropsWithChildren } from "react";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AppSidebar from "./AppSidebar";

const { loadMobileSidebarDrawer, preloadAppRoute } = vi.hoisted(() => ({
  loadMobileSidebarDrawer: vi.fn(),
  preloadAppRoute: vi.fn(),
}));

vi.mock("../routes/RoutePreloadContext", () => ({ useRoutePreload: () => preloadAppRoute }));
vi.mock("./mobileSidebarDrawerLoader", () => ({ loadMobileSidebarDrawer }));

describe("AppSidebar", () => {
  beforeEach(() => {
    preloadAppRoute.mockReset();
    loadMobileSidebarDrawer.mockReset().mockResolvedValue({
      default: ({ children }: PropsWithChildren) => <aside data-testid="mobile-sidebar-drawer">{children}</aside>,
    });
  });

  it("does not load the mobile Drawer for the desktop sidebar", async () => {
    await act(async () => {
      render(
        <AppSidebar
          activeKey="/"
          collapsed={false}
          isMobile={false}
          mobileNavOpen={false}
          themeKey="stellar-blue"
          onCollapse={vi.fn()}
          onMobileNavClose={vi.fn()}
          onNavigate={vi.fn()}
        />,
      );
      await Promise.resolve();
    });

    expect(screen.getByRole("complementary")).toBeInTheDocument();
    expect(loadMobileSidebarDrawer).not.toHaveBeenCalled();
  });

  it("preloads a page when its navigation label is hovered", async () => {
    render(
      <AppSidebar
        activeKey="/"
        collapsed={false}
        isMobile={false}
        mobileNavOpen={false}
        themeKey="stellar-blue"
        onCollapse={vi.fn()}
        onMobileNavClose={vi.fn()}
        onNavigate={vi.fn()}
      />,
    );

    await act(async () => {
      fireEvent.pointerEnter(screen.getByText("量化"));
      await Promise.resolve();
    });

    expect(preloadAppRoute).toHaveBeenCalledWith("/quant");
  });

  it("preloads a page when its menu item receives keyboard focus", async () => {
    render(
      <AppSidebar
        activeKey="/"
        collapsed={false}
        isMobile={false}
        mobileNavOpen={false}
        themeKey="stellar-blue"
        onCollapse={vi.fn()}
        onMobileNavClose={vi.fn()}
        onNavigate={vi.fn()}
      />,
    );

    const marketItem = screen.getByRole("button", { name: "市场" });
    await act(async () => {
      fireEvent.focus(marketItem);
      await Promise.resolve();
    });

    expect(preloadAppRoute).toHaveBeenCalledWith("/market");
  });

  it("places chat directly below market in the common navigation", async () => {
    render(
      <AppSidebar
        activeKey="/"
        collapsed={false}
        isMobile={false}
        mobileNavOpen={false}
        themeKey="stellar-blue"
        onCollapse={vi.fn()}
        onMobileNavClose={vi.fn()}
        onNavigate={vi.fn()}
      />,
    );
    await act(async () => {
      await Promise.resolve();
    });

    const menuItems = within(screen.getByRole("navigation", { name: "主导航" }))
      .getAllByRole("button")
      .map((item) => item.textContent);

    expect(menuItems.slice(0, 4)).toEqual(["首页", "市场", "对话", "资讯"]);
  });

  it("marks the active route and navigates from native controls", () => {
    const onNavigate = vi.fn();
    render(
      <AppSidebar
        activeKey="/market"
        collapsed={false}
        isMobile={false}
        mobileNavOpen={false}
        themeKey="stellar-blue"
        onCollapse={vi.fn()}
        onMobileNavClose={vi.fn()}
        onNavigate={onNavigate}
      />,
    );

    expect(screen.getByRole("button", { name: "市场" })).toHaveAttribute("aria-current", "page");
    fireEvent.click(screen.getByRole("button", { name: "量化" }));
    expect(onNavigate).toHaveBeenCalledWith("/quant");
  });

  it("labels the analysis route as individual stock and preserves its route", () => {
    const onNavigate = vi.fn();
    render(
      <AppSidebar
        activeKey="/analysis"
        collapsed={false}
        isMobile={false}
        mobileNavOpen={false}
        themeKey="stellar-blue"
        onCollapse={vi.fn()}
        onMobileNavClose={vi.fn()}
        onNavigate={onNavigate}
      />,
    );

    const stockItem = screen.getByRole("button", { name: "个股" });
    expect(stockItem).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("button", { name: "分析" })).not.toBeInTheDocument();
    fireEvent.click(stockItem);
    expect(onNavigate).toHaveBeenCalledWith("/analysis");
  });

  it("keeps collapsed routes accessible without visible labels", () => {
    render(
      <AppSidebar
        activeKey="/"
        collapsed
        isMobile={false}
        mobileNavOpen={false}
        themeKey="stellar-blue"
        onCollapse={vi.fn()}
        onMobileNavClose={vi.fn()}
        onNavigate={vi.fn()}
      />,
    );

    const marketItem = screen.getByRole("button", { name: "市场" });
    expect(marketItem).toHaveAttribute("title", "市场");
    expect(marketItem).not.toHaveTextContent("市场");
  });

  it("loads the Drawer boundary on mobile viewports", async () => {
    render(
      <AppSidebar
        activeKey="/market"
        collapsed={false}
        isMobile
        mobileNavOpen
        themeKey="stellar-blue"
        onCollapse={vi.fn()}
        onMobileNavClose={vi.fn()}
        onNavigate={vi.fn()}
      />,
    );

    expect(await screen.findByTestId("mobile-sidebar-drawer")).toBeInTheDocument();
    expect(loadMobileSidebarDrawer).toHaveBeenCalledTimes(1);
  });
});
