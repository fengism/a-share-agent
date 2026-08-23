import { lazy, Suspense, useEffect, useLayoutEffect, useMemo } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import { useThemeStore, tokensToCssVars } from "./styles/ui";
import { themes } from "./theme/themes";
import "./styles/base.css";
import "./styles/markdown.css";
import "./styles/analysis-export.css";
import RequireAuth from "./components/RequireAuth";
import ErrorBoundary from "./components/ErrorBoundary";
import RouteLoadingFallback from "./components/RouteLoadingFallback";
import { useAuthStore } from "./store/authStore";
import { queryClient } from "./api/queryClient";
import { pageLoaders, preloadAppRoute } from "./routes/pageLoaders";
import RoutePreloadProvider from "./routes/RoutePreloadProvider";

// ── 路由级代码分割 ──
const AppLayout = lazy(pageLoaders.appLayout);
const Dashboard = lazy(pageLoaders.dashboard);
const Market = lazy(pageLoaders.market);
const Screener = lazy(pageLoaders.screener);
const Analysis = lazy(pageLoaders.analysis);
const AnalysisEntry = lazy(pageLoaders.analysisEntry);
const DailyReviewPage = lazy(pageLoaders.dailyReview);
const PotentialPage = lazy(pageLoaders.potential);
const Chat = lazy(pageLoaders.chat);
const Settings = lazy(pageLoaders.settings);
const Feed = lazy(pageLoaders.feed);
const Twitter = lazy(pageLoaders.twitter);
const IndustryChain = lazy(pageLoaders.industryChain);
const Compare = lazy(pageLoaders.compare);
const Macro = lazy(pageLoaders.macro);
const Portfolio = lazy(pageLoaders.portfolio);
const Quant = lazy(pageLoaders.quant);
const Capabilities = lazy(pageLoaders.capabilities);
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
    const cc = meta.colors;
    const vars: Record<string, string> = {
      "--c-page-bg": cc.pageBg,
      "--c-card-bg": cc.cardBg,
      "--c-elevated-bg": cc.elevatedBg,
      "--c-nested-bg": cc.nestedBg,
      "--c-primary": cc.primary,
      "--c-accent": cc.accent,
      "--c-up": cc.up,
      "--c-down": cc.down,
      "--c-text-primary": cc.textPrimary,
      "--c-text-secondary": cc.textSecondary,
      "--c-text-muted": cc.textMuted,
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
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "微软雅黑", "Helvetica Neue", Arial, sans-serif',
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

export default function App() {
  // Validate the HttpOnly cookie session once before protected routes render.
  useEffect(() => {
    useAuthStore.getState().bootstrap();
  }, []);

  return (
    <AntProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <RoutePreloadProvider preload={preloadAppRoute}>
            <ErrorBoundary>
              <Suspense fallback={<RouteLoadingFallback />}>
                <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route path="/reset-password" element={<ResetPassword />} />
                <Route element={<RequireAuth />}>
                <Route path="/force-change-password" element={<ErrorBoundary><ForceChangePassword /></ErrorBoundary>} />
                <Route element={<AppLayout />}>
                  <Route path="/" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
                  <Route path="/market" element={<ErrorBoundary><Market /></ErrorBoundary>} />
                  <Route path="/screener" element={<ErrorBoundary><Screener /></ErrorBoundary>} />
                  <Route path="/daily-review" element={<ErrorBoundary><DailyReviewPage /></ErrorBoundary>} />
                <Route path="/potential" element={<ErrorBoundary><PotentialPage /></ErrorBoundary>} />
                  <Route path="/feed" element={<ErrorBoundary><Feed /></ErrorBoundary>} />
                  <Route path="/twitter" element={<ErrorBoundary><Twitter /></ErrorBoundary>} />
                  <Route path="/analysis" element={<ErrorBoundary><AnalysisEntry /></ErrorBoundary>} />
                  <Route path="/macro" element={<ErrorBoundary><Macro /></ErrorBoundary>} />
                  <Route path="/compare" element={<ErrorBoundary><Compare /></ErrorBoundary>} />
                  <Route path="/portfolio" element={<ErrorBoundary><Portfolio /></ErrorBoundary>} />
                  <Route path="/quant" element={<ErrorBoundary><Quant /></ErrorBoundary>} />
                  <Route path="/industry-chain" element={<ErrorBoundary><IndustryChain /></ErrorBoundary>} />
                  <Route path="/industry-chain/:name" element={<ErrorBoundary><IndustryChain /></ErrorBoundary>} />
                  <Route path="/chat" element={<ErrorBoundary><Chat /></ErrorBoundary>} />
                  <Route path="/capabilities" element={<ErrorBoundary><Capabilities /></ErrorBoundary>} />
                  <Route path="/settings" element={<ErrorBoundary><Settings /></ErrorBoundary>} />
                  <Route path="/analysis/:code" element={<ErrorBoundary><Analysis /></ErrorBoundary>} />
                </Route>
                </Route>
                </Routes>
              </Suspense>
            </ErrorBoundary>
          </RoutePreloadProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </AntProvider>
  );
}
