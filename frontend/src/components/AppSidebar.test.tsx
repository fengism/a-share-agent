import type { PropsWithChildren } from "react";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { themes } from "../theme/themes";
import AppSidebar from "./AppSidebar";
import { getActiveNavKey } from "./navConfig";

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

  it("orders sidebar entries by the four investment workspaces", async () => {
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

    // 4 个工作区：盯盘中心 → 市场洞察 → 深度投研 → 策略与复盘，尾部为运维工具区。
    // 顺序即信息架构，改动这里应是有意为之，而不是顺手调序。
    expect(menuItems).toEqual([
      // 盯盘中心
      "首页",
      "自选",
      "市场",
      "概念",
      // 市场洞察
      "韭菜指数",
      "国家队",
      "宏观",
      "产业链",
      "资讯",
      // 深度投研
      "对话",
      "个股",
      "选股",
      "潜力股",
      // 策略与复盘
      "仓位",
      "量化",
      "复盘",
      "交易日历",
      // 运维工具区（无分组标题）
      "主数据管理",
    ]);
    expect(menuItems).not.toContain("港股市场");
  });

  it("opens and preloads the national team holdings page", async () => {
    const onNavigate = vi.fn();
    render(
      <AppSidebar
        activeKey="/national-team"
        collapsed={false}
        isMobile={false}
        mobileNavOpen={false}
        themeKey="stellar-blue"
        onCollapse={vi.fn()}
        onMobileNavClose={vi.fn()}
        onNavigate={onNavigate}
      />,
    );

    const item = screen.getByRole("button", { name: "国家队" });
    expect(item).toHaveAttribute("aria-current", "page");
    await act(async () => {
      fireEvent.pointerEnter(item);
      await Promise.resolve();
    });
    expect(preloadAppRoute).toHaveBeenCalledWith("/national-team");
    fireEvent.click(item);
    expect(onNavigate).toHaveBeenCalledWith("/national-team");
  });

  it("places the trading calendar in the lower tool navigation", () => {
    const onNavigate = vi.fn();
    render(
      <AppSidebar
        activeKey="/trading-calendar"
        collapsed={false}
        isMobile={false}
        mobileNavOpen={false}
        themeKey="stellar-blue"
        onCollapse={vi.fn()}
        onMobileNavClose={vi.fn()}
        onNavigate={onNavigate}
      />,
    );

    const navigation = within(screen.getByRole("navigation", { name: "主导航" }));
    const menuItems = navigation.getAllByRole("button").map((item) => item.textContent);
    expect(menuItems.slice(-2)).toEqual(["交易日历", "主数据管理"]);
    expect(menuItems).not.toContain("设置");
    expect(menuItems).not.toContain("能力");

    const calendarItem = navigation.getByRole("button", { name: "交易日历" });
    expect(calendarItem).toHaveAttribute("aria-current", "page");
    fireEvent.click(calendarItem);
    expect(onNavigate).toHaveBeenCalledWith("/trading-calendar");
  });

  it("opens and preloads the master data management page", async () => {
    const onNavigate = vi.fn();
    render(
      <AppSidebar
        activeKey="/master-data"
        collapsed={false}
        isMobile={false}
        mobileNavOpen={false}
        themeKey="stellar-blue"
        onCollapse={vi.fn()}
        onMobileNavClose={vi.fn()}
        onNavigate={onNavigate}
      />,
    );

    const industryItem = screen.getByRole("button", { name: "主数据管理" });
    expect(industryItem).toHaveAttribute("aria-current", "page");
    await act(async () => {
      fireEvent.pointerEnter(industryItem);
      await Promise.resolve();
    });
    expect(preloadAppRoute).toHaveBeenCalledWith("/master-data");

    fireEvent.click(industryItem);
    expect(onNavigate).toHaveBeenCalledWith("/master-data");
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

  it("uses one unified stock research entry", () => {
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
    expect(screen.queryByRole("button", { name: "投资研究" })).not.toBeInTheDocument();
    fireEvent.click(stockItem);
    expect(onNavigate).toHaveBeenCalledWith("/analysis");
  });

  it("keeps Twitter inside the unified information entry", () => {
    render(
      <AppSidebar
        activeKey="/feed"
        collapsed={false}
        isMobile={false}
        mobileNavOpen={false}
        themeKey="stellar-blue"
        onCollapse={vi.fn()}
        onMobileNavClose={vi.fn()}
        onNavigate={vi.fn()}
      />,
    );

    const navigation = within(screen.getByRole("navigation", { name: "主导航" }));
    expect(navigation.getByRole("button", { name: "资讯" })).toHaveAttribute("aria-current", "page");
    expect(navigation.queryByRole("button", { name: "Twitter/X" })).not.toBeInTheDocument();
  });

  it("does not expose a second investment research navigation item", () => {
    render(
      <AppSidebar
        activeKey="/analysis"
        collapsed={false}
        isMobile={false}
        mobileNavOpen={false}
        themeKey="stellar-blue"
        onCollapse={vi.fn()}
        onMobileNavClose={vi.fn()}
        onNavigate={vi.fn()}
      />,
    );

    const navigation = within(screen.getByRole("navigation", { name: "主导航" }));
    const labels = navigation.getAllByRole("button").map((item) => item.textContent);
    expect(labels).toContain("个股");
    expect(labels).not.toContain("投资研究");
    expect(labels).not.toContain("对比");
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

  it("loads the Drawer boundary on mobile viewports and allows closing", async () => {
    const onMobileNavClose = vi.fn();
    render(
      <AppSidebar
        activeKey="/market"
        collapsed={false}
        isMobile
        mobileNavOpen
        themeKey="stellar-blue"
        onCollapse={vi.fn()}
        onMobileNavClose={onMobileNavClose}
        onNavigate={vi.fn()}
      />,
    );

    expect(await screen.findByTestId("mobile-sidebar-drawer")).toBeInTheDocument();
    expect(loadMobileSidebarDrawer).toHaveBeenCalledTimes(1);

    const closeBtn = screen.getByRole("button", { name: "关闭侧边栏" });
    expect(closeBtn).toBeInTheDocument();
    fireEvent.click(closeBtn);
    expect(onMobileNavClose).toHaveBeenCalledTimes(1);
  });

  it("applies light theme background when themeKey is light", () => {
    render(
      <AppSidebar
        activeKey="/"
        collapsed={false}
        isMobile={false}
        mobileNavOpen={false}
        themeKey="light"
        onCollapse={vi.fn()}
        onMobileNavClose={vi.fn()}
        onNavigate={vi.fn()}
      />,
    );

    const aside = screen.getByRole("complementary", { name: "应用侧栏" });
    expect(aside).toHaveStyle({ background: themes.light.siderBg });
  });

  it("renders dividers between groups in collapsed mode", () => {
    const { container } = render(
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

    const dividers = container.querySelectorAll(".app-sidebar-nav__divider");
    expect(dividers.length).toBeGreaterThan(0);
  });

  it("correctly resolves active navigation keys via getActiveNavKey", () => {
    expect(getActiveNavKey("/")).toBe("/");
    expect(getActiveNavKey("/watchlist")).toBe("/watchlist");
    expect(getActiveNavKey("/hk-market")).toBe("/market");
    expect(getActiveNavKey("/market/overview")).toBe("/market");
    expect(getActiveNavKey("/stock/600519")).toBe("/analysis");
    expect(getActiveNavKey("/investment-research/report")).toBe("/analysis");
    expect(getActiveNavKey("/analysis/detail")).toBe("/analysis");
    expect(getActiveNavKey("/industry-classification")).toBe("/master-data");
    expect(getActiveNavKey("/stock-concept")).toBe("/master-data");
    expect(getActiveNavKey("/master-data")).toBe("/master-data");
    expect(getActiveNavKey("/twitter")).toBe("/feed");
    expect(getActiveNavKey("/feed")).toBe("/feed");
    expect(getActiveNavKey("/settings")).toBe("/");
    expect(getActiveNavKey("/capabilities")).toBe("/");
    expect(getActiveNavKey("/unknown-path")).toBe("/");
  });
});
