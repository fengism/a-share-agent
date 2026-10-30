import { Navigate, createBrowserRouter, type RouteObject } from "react-router-dom";
import RequireAuth from "../components/RequireAuth";
import ErrorBoundary from "../components/ErrorBoundary";
import LegacyResearchRedirect from "./LegacyResearchRedirect";

/**
 * 路由表所需的页面组件集合。
 *
 * 抽成参数而不是在模块里直接 `import`，这样同一份路由表既可用于应用入口，
 * 也能在测试中注入占位组件做导航回归（无需拉起真实页面与数据请求）。
 */
export interface AppRouteComponents {
  AppLayout: React.ComponentType;
  EarthScope: React.ComponentType;
  Dashboard: React.ComponentType;
  Watchlist: React.ComponentType;
  Market: React.ComponentType;
  NationalTeam: React.ComponentType;
  TradingCalendar: React.ComponentType;
  Screener: React.ComponentType;
  Analysis: React.ComponentType;
  Concept: React.ComponentType;
  Stock: React.ComponentType;
  AnalysisEntry: React.ComponentType;
  DailyReview: React.ComponentType;
  Potential: React.ComponentType;
  Chat: React.ComponentType;
  Settings: React.ComponentType;
  Feed: React.ComponentType;
  IndustryChain: React.ComponentType;
  Macro: React.ComponentType;
  Portfolio: React.ComponentType;
  Quant: React.ComponentType;
  Capabilities: React.ComponentType;
  MasterData: React.ComponentType;
  Login: React.ComponentType;
  Register: React.ComponentType;
  ResetPassword: React.ComponentType;
  ForceChangePassword: React.ComponentType;
}

/**
 * 构建应用路由（data router）。
 *
 * 使用 `createBrowserRouter` 而非声明式 `<Routes>`：只有 data router 才提供
 * `useBlocker`，设置页等"未保存表单"页面需要它来做站内离开拦截。
 */
export function buildAppRoutes(components: AppRouteComponents): RouteObject[] {
  const {
    AppLayout, EarthScope, Dashboard, Watchlist, Market, NationalTeam, TradingCalendar,
    Screener, Analysis, Concept, Stock, AnalysisEntry, DailyReview, Potential, Chat,
    Settings, Feed, IndustryChain, Macro, Portfolio, Quant, Capabilities, MasterData,
    Login, Register, ResetPassword, ForceChangePassword,
  } = components;

  return [
    { path: "/earthscope", element: <EarthScope /> },
    { path: "/login", element: <Login /> },
    { path: "/register", element: <Register /> },
    { path: "/reset-password", element: <ResetPassword /> },
    {
      element: <RequireAuth />,
      children: [
        {
          path: "/force-change-password",
          element: <ErrorBoundary><ForceChangePassword /></ErrorBoundary>,
        },
        {
          element: <AppLayout />,
          children: [
            { path: "/", element: <ErrorBoundary><Dashboard /></ErrorBoundary> },
            { path: "/watchlist", element: <ErrorBoundary><Watchlist /></ErrorBoundary> },
            { path: "/market", element: <ErrorBoundary><Market /></ErrorBoundary> },
            { path: "/national-team", element: <ErrorBoundary><NationalTeam /></ErrorBoundary> },
            { path: "/hk-market", element: <Navigate to="/market?market=hk" replace /> },
            { path: "/trading-calendar", element: <ErrorBoundary><TradingCalendar /></ErrorBoundary> },
            { path: "/screener", element: <ErrorBoundary><Screener /></ErrorBoundary> },
            { path: "/daily-review", element: <ErrorBoundary><DailyReview /></ErrorBoundary> },
            { path: "/potential", element: <ErrorBoundary><Potential /></ErrorBoundary> },
            { path: "/feed", element: <ErrorBoundary><Feed /></ErrorBoundary> },
            { path: "/twitter", element: <Navigate to="/feed?tab=twitter" replace /> },
            { path: "/analysis", element: <ErrorBoundary><AnalysisEntry /></ErrorBoundary> },
            { path: "/stock", element: <Navigate to="/analysis" replace /> },
            { path: "/investment-research", element: <Navigate to="/analysis" replace /> },
            { path: "/investment-research/:code", element: <LegacyResearchRedirect /> },
            { path: "/macro", element: <ErrorBoundary><Macro /></ErrorBoundary> },
            { path: "/compare", element: <Navigate to="/screener" replace /> },
            { path: "/portfolio", element: <ErrorBoundary><Portfolio /></ErrorBoundary> },
            { path: "/quant", element: <ErrorBoundary><Quant /></ErrorBoundary> },
            { path: "/industry-chain", element: <ErrorBoundary><IndustryChain /></ErrorBoundary> },
            { path: "/industry-chain/:name", element: <ErrorBoundary><IndustryChain /></ErrorBoundary> },
            { path: "/chat", element: <ErrorBoundary><Chat /></ErrorBoundary> },
            { path: "/capabilities", element: <ErrorBoundary><Capabilities /></ErrorBoundary> },
            { path: "/master-data", element: <ErrorBoundary><MasterData /></ErrorBoundary> },
            { path: "/stock-concept", element: <Navigate to="/master-data?tab=concept" replace /> },
            { path: "/industry-classification", element: <Navigate to="/master-data?tab=industry" replace /> },
            { path: "/settings", element: <ErrorBoundary><Settings /></ErrorBoundary> },
            { path: "/concept", element: <ErrorBoundary><Concept /></ErrorBoundary> },
            { path: "/stock/:code", element: <ErrorBoundary><Stock /></ErrorBoundary> },
            { path: "/analysis/:code", element: <ErrorBoundary><Analysis /></ErrorBoundary> },
          ],
        },
      ],
    },
  ];
}

export function createAppRouter(components: AppRouteComponents) {
  return createBrowserRouter(buildAppRoutes(components));
}
