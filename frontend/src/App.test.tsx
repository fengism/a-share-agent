import { render, screen, waitFor } from "@testing-library/react";
import { Outlet, RouterProvider, createMemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { buildAppRoutes, type AppRouteComponents } from "./routes/appRoutes";
import { useAuthStore } from "./store/authStore";

/**
 * 入口路由回归。
 *
 * 直接对 `buildAppRoutes` 注入占位组件，验证 data router 迁移后
 * 守卫重定向、别名重定向与受保护页面行为未变（不拉起真实页面与请求）。
 */
function stub(label: string) {
  return () => <div>{label}</div>;
}

const components = {
  // 与真实 AppLayout 一样只需渲染子路由，避免引入整页依赖
  AppLayout: () => <Outlet />,
  EarthScope: stub("地球内容"),
  Dashboard: stub("首页内容"),
  Watchlist: stub("自选内容"),
  Market: stub("市场内容"),
  NationalTeam: stub("国家队内容"),
  TradingCalendar: stub("交易日历内容"),
  Screener: stub("选股内容"),
  Analysis: stub("分析内容"),
  Concept: stub("概念内容"),
  Stock: stub("个股内容"),
  AnalysisEntry: stub("分析入口内容"),
  DailyReview: stub("复盘内容"),
  Potential: stub("潜力内容"),
  Chat: stub("对话内容"),
  Settings: stub("设置内容"),
  Feed: stub("资讯内容"),
  IndustryChain: stub("产业链内容"),
  Macro: stub("宏观内容"),
  Portfolio: stub("组合内容"),
  Quant: stub("量化内容"),
  Capabilities: stub("能力内容"),
  MasterData: stub("主数据内容"),
  Login: stub("登录内容"),
  Register: stub("注册内容"),
  ResetPassword: stub("重置内容"),
  ForceChangePassword: stub("强制改密内容"),
} as unknown as AppRouteComponents;

function renderAt(path: string) {
  const router = createMemoryRouter(buildAppRoutes(components), { initialEntries: [path] });
  render(<RouterProvider router={router} />);
  return router;
}

describe("app routes (data router)", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, bootstrapped: true });
  });

  it("redirects unauthenticated users from a protected route to /login", async () => {
    const router = renderAt("/settings");

    expect(await screen.findByText("登录内容")).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  });

  it("renders the protected page for an authenticated user", async () => {
    useAuthStore.setState({
      user: { id: 1, username: "admin", is_admin: true, must_change_password: false },
      bootstrapped: true,
    });

    renderAt("/watchlist");

    expect(await screen.findByText("自选内容")).toBeInTheDocument();
  });

  it("sends users with a pending password change to the force-change route", async () => {
    useAuthStore.setState({
      user: { id: 1, username: "admin", is_admin: true, must_change_password: true },
      bootstrapped: true,
    });
    const router = renderAt("/watchlist");

    await waitFor(() => expect(router.state.location.pathname).toBe("/force-change-password"));
  });

  it("keeps the legacy alias redirects working", async () => {
    useAuthStore.setState({
      user: { id: 1, username: "admin", is_admin: true, must_change_password: false },
      bootstrapped: true,
    });
    const router = renderAt("/stock");

    await waitFor(() => expect(router.state.location.pathname).toBe("/analysis"));
  });

  it("keeps the HK market alias including its query string", async () => {
    useAuthStore.setState({
      user: { id: 1, username: "admin", is_admin: true, must_change_password: false },
      bootstrapped: true,
    });
    const router = renderAt("/hk-market");

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/market");
      expect(router.state.location.search).toBe("?market=hk");
    });
  });
});
