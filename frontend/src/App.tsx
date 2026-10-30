import { lazy, Suspense, useEffect, useLayoutEffect, useMemo } from "react";
import { RouterProvider } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import { useThemeStore, tokensToCssVars } from "./styles/ui";
import { themes } from "./theme/themes";
import { APP_FONT_FAMILY, APP_MONO_FONT_FAMILY } from "./theme/typography";
import "./styles/base.css";
import "./styles/markdown.css";
import "./styles/analysis-export.css";
import ErrorBoundary from "./components/ErrorBoundary";
import RouteLoadingFallback from "./components/RouteLoadingFallback";
import { useAuthStore } from "./store/authStore";
import { queryClient } from "./api/queryClient";
import { pageLoaders, preloadAppRoute } from "./routes/pageLoaders";
import RoutePreloadProvider from "./routes/RoutePreloadProvider";
import { createAppRouter } from "./routes/appRoutes";

// ── 路由级代码分割 ──
const AppLayout = lazy(pageLoaders.appLayout);
const EarthScope = lazy(pageLoaders.earthscope);
const Dashboard = lazy(pageLoaders.dashboard);
const Watchlist = lazy(pageLoaders.watchlist);
const Market = lazy(pageLoaders.market);
const NationalTeam = lazy(pageLoaders.nationalTeam);
const TradingCalendar = lazy(pageLoaders.tradingCalendar);
const Screener = lazy(pageLoaders.screener);
const Analysis = lazy(pageLoaders.analysis);
const Concept = lazy(pageLoaders.concept);
const Stock = lazy(pageLoaders.stock);
const AnalysisEntry = lazy(pageLoaders.analysisEntry);
const DailyReviewPage = lazy(pageLoaders.dailyReview);
const PotentialPage = lazy(pageLoaders.potential);
const Chat = lazy(pageLoaders.chat);
const Settings = lazy(pageLoaders.settings);
const Feed = lazy(pageLoaders.feed);
const IndustryChain = lazy(pageLoaders.industryChain);
const Macro = lazy(pageLoaders.macro);
const Portfolio = lazy(pageLoaders.portfolio);
const Quant = lazy(pageLoaders.quant);
const Capabilities = lazy(pageLoaders.capabilities);
const MasterData = lazy(pageLoaders.masterData);
const Login = lazy(pageLoaders.login);
const Register = lazy(pageLoaders.register);
const ResetPassword = lazy(pageLoaders.resetPassword);
const ForceChangePassword = lazy(pageLoaders.forceChangePassword);

function AntProvider({ children }: { children: React.ReactNode }) {
  const themeKey = useThemeStore((s) => s.themeKey);
  const meta = themes[themeKey];
  const token = meta.antToken;

  // Expose the active theme's colors as CSS custom properties on <html>,
  // so CSS :hover rules (see base.css) can react to theme changes without
  // per-element JS handlers. Single source of truth: theme/themes.ts.
  useLayoutEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", themeKey);
    root.style.colorScheme = meta.isLight ? "light" : "dark";
    root.style.background = meta.colors.pageBg;
    if (document.body) {
      document.body.style.background = meta.colors.pageBg;
    }
    const cc = meta.colors;
    const vars: Record<string, string> = {
      "--boot-bg": cc.pageBg,
      "--boot-fg": cc.textPrimary,
      "--c-page-bg": cc.pageBg,
      "--c-card-bg": cc.cardBg,
      "--c-elevated-bg": cc.elevatedBg,
      "--c-nested-bg": cc.nestedBg,
      "--c-bg-subtle": cc.nestedBg,
      "--c-bg-soft": cc.nestedBg,
      "--c-border-subtle": cc.border,
      "--c-primary": cc.primary,
      "--c-accent": cc.accent,
      "--c-up": cc.up,
      "--c-down": cc.down,
      "--c-text-primary": cc.textPrimary,
      "--c-text-secondary": cc.textSecondary,
      "--c-text-muted": cc.textMuted,
      "--c-text-subtle": cc.textMuted,
      "--c-text": cc.textPrimary,
      "--c-border": cc.border,
      "--c-focus-ring": cc.focusRing,
      "--c-surface-overlay": cc.surfaceOverlay,
      "--c-auth-background": cc.authBackground,
      "--c-auth-hero-gradient": cc.authHeroGradient,
      "--c-card-shadow": cc.cardShadow,
      "--c-hover-bg": cc.hoverBg,
      "--c-active-bg": cc.activeBg,
      "--c-primary-soft": `${cc.primary}14`,
      "--c-primary-2": `${cc.primary}26`,
      "--c-primary-3": `${cc.primary}4d`,
      "--c-muted-soft": `${cc.textMuted}14`,
      "--c-font-sans": APP_FONT_FAMILY,
      "--c-font-mono": APP_MONO_FONT_FAMILY,
      "--c-sider-bg": meta.siderBg,
      "--c-header-bg": meta.headerBg,
      ...tokensToCssVars(meta),
    };
    for (const k in vars) root.style.setProperty(k, vars[k]);
  }, [themeKey, meta]);

  const antTheme = useMemo(
    () => ({
      algorithm: meta.isLight ? theme.defaultAlgorithm : theme.darkAlgorithm,
      token: {
        ...token,
        borderRadius: 8,
        fontSize: 14,
        fontSizeSM: 12,
        fontSizeLG: 16,
        fontSizeXL: 20,
        fontFamily: APP_FONT_FAMILY,
        fontWeightStrong: 600,
        lineHeight: 1.5,
      },
      components: {
        // Institutional/terminal table feel: subtle header band, crisp
        // hairline separators, quiet row hover — applied app-wide.
        Table: {
          headerBg: meta.colors.nestedBg,
          headerColor: meta.colors.textSecondary,
          borderColor: meta.colors.border,
          rowHoverBg: meta.colors.hoverBg,
          headerSplitColor: "transparent",
        },
        // Keep antd Card elevation aligned with the design-token shadow so
        // Cards, `.u-card` and inline cardStyle share one shadow scale.
        Card: {
          boxShadowTertiary: meta.tokens.shadow.xs,
        },
        // On-brand Tab nav: muted inactive labels, brand-primary active text
        // and ink bar, plus a slightly more breathable gutter/padding so
        // icon+label tabs (e.g. Market's 7 tabs) don't feel cramped.
        Tabs: {
          itemColor: meta.colors.textSecondary,
          itemHoverColor: meta.colors.textPrimary,
          itemSelectedColor: meta.colors.primary,
          inkBarColor: meta.colors.primary,
          horizontalItemGutter: 16,
          horizontalItemPadding: "8px 4px",
          titleFontSize: 14,
        },
        // Borderless tags read as quiet inline labels (e.g. "每 60 秒刷新")
        // instead of light-filled chips — the dark-theme background stays the
        // card color, with only a hairline border + secondary text.
        Tag: {
          defaultBg: "transparent",
          defaultColor: meta.colors.textSecondary,
        },
      },
    }),
    [meta, token],
  );

  return (
    <ConfigProvider
      locale={zhCN}
      theme={antTheme}
    >
      {children}
    </ConfigProvider>
  );
}

/**
 * 路由表（data router）。
 *
 * 使用 `createBrowserRouter` 而非声明式 `<Routes>`：只有 data router 才提供
 * `useBlocker`，设置页等"未保存表单"页面需要它来做站内离开拦截。
 */
const router = createAppRouter({
  AppLayout,
  EarthScope,
  Dashboard,
  Watchlist,
  Market,
  NationalTeam,
  TradingCalendar,
  Screener,
  Analysis,
  Concept,
  Stock,
  AnalysisEntry,
  DailyReview: DailyReviewPage,
  Potential: PotentialPage,
  Chat,
  Settings,
  Feed,
  IndustryChain,
  Macro,
  Portfolio,
  Quant,
  Capabilities,
  MasterData,
  Login,
  Register,
  ResetPassword,
  ForceChangePassword,
});

export default function App() {
  // Validate the HttpOnly cookie session once before protected routes render.
  useEffect(() => {
    useAuthStore.getState().bootstrap();
  }, []);

  return (
    <AntProvider>
      <QueryClientProvider client={queryClient}>
        <RoutePreloadProvider preload={preloadAppRoute}>
          <ErrorBoundary>
            <Suspense fallback={<RouteLoadingFallback />}>
              <RouterProvider router={router} />
            </Suspense>
          </ErrorBoundary>
        </RoutePreloadProvider>
      </QueryClientProvider>
    </AntProvider>
  );
}
