import { lazy, Suspense, useEffect, useLayoutEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider, Spin, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import { useThemeStore, getAntToken } from "./styles/ui";
import { themes } from "./theme/themes";
import "./styles/base.css";
import "./styles/markdown.css";
import "./styles/analysis-export.css";
import AppLayout from "./components/AppLayout";
import RequireAuth from "./components/RequireAuth";
import ErrorBoundary from "./components/ErrorBoundary";
import { useAuthStore } from "./store/authStore";

// ── 路由级代码分割 ──
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Market = lazy(() => import("./pages/Market"));
const Screener = lazy(() => import("./pages/Screener"));
const Analysis = lazy(() => import("./pages/Analysis"));
const AnalysisEntry = lazy(() => import("./pages/Analysis/Entry"));
const DailyReviewPage = lazy(() => import("./pages/DailyReview"));
const Chat = lazy(() => import("./pages/Chat"));
const Settings = lazy(() => import("./pages/Settings"));
const Feed = lazy(() => import("./pages/Feed"));
const IndustryChain = lazy(() => import("./pages/IndustryChain"));
const Compare = lazy(() => import("./pages/Compare"));
const Macro = lazy(() => import("./pages/Macro"));
const Login = lazy(() => import("./pages/Login"));
const Register = lazy(() => import("./pages/Register"));
const ResetPassword = lazy(() => import("./pages/ResetPassword"));
const ForceChangePassword = lazy(() => import("./pages/ForceChangePassword"));

const queryClient = new QueryClient({
  defaultOptions: {
    // Global default staleTime — safety net so any query without its own
    // staleTime doesn't fall back to 0 (refetch on every mount). Individual
    // queries still override this with their own tuned values.
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 60 * 1000 },
  },
});

function AntProvider({ children }: { children: React.ReactNode }) {
  const themeKey = useThemeStore((s) => s.themeKey);
  const meta = themes[themeKey];
  const token = getAntToken();

  // Expose the active theme's colors as CSS custom properties on <html>,
  // so CSS :hover rules (see base.css) can react to theme changes without
  // per-element JS handlers. Single source of truth: theme/themes.ts.
  useLayoutEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", themeKey);
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
      "--c-primary-soft": `${cc.primary}14`,
      "--c-primary-2": `${cc.primary}26`,
      "--c-primary-3": `${cc.primary}4d`,
      "--c-muted-soft": `${cc.textMuted}14`,
    };
    for (const k in vars) root.style.setProperty(k, vars[k]);
  }, [themeKey, meta]);

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: meta.isLight ? theme.defaultAlgorithm : theme.darkAlgorithm,
        token: {
          ...token,
          borderRadius: 8,
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
            rowHoverBg: meta.colors.elevatedBg,
            headerSplitColor: "transparent",
          },
        },
      }}
    >
      {children}
    </ConfigProvider>
  );
}

const PageFallback = (
  <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "50vh" }}>
    <Spin size="large" tip="加载中..." />
  </div>
);

export default function App() {
  // Validate a persisted token once on startup, then RequireAuth can render.
  useEffect(() => {
    useAuthStore.getState().bootstrap();
  }, []);

  return (
    <AntProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ErrorBoundary>
            <Suspense fallback={PageFallback}>
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
                  <Route path="/feed" element={<ErrorBoundary><Feed /></ErrorBoundary>} />
                  <Route path="/analysis" element={<ErrorBoundary><AnalysisEntry /></ErrorBoundary>} />
                  <Route path="/macro" element={<ErrorBoundary><Macro /></ErrorBoundary>} />
                  <Route path="/compare" element={<ErrorBoundary><Compare /></ErrorBoundary>} />
                  <Route path="/industry-chain" element={<ErrorBoundary><IndustryChain /></ErrorBoundary>} />
                  <Route path="/industry-chain/:name" element={<ErrorBoundary><IndustryChain /></ErrorBoundary>} />
                  <Route path="/chat" element={<ErrorBoundary><Chat /></ErrorBoundary>} />
                  <Route path="/settings" element={<ErrorBoundary><Settings /></ErrorBoundary>} />
                  <Route path="/analysis/:code" element={<ErrorBoundary><Analysis /></ErrorBoundary>} />
                </Route>
                </Route>
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </BrowserRouter>
      </QueryClientProvider>
    </AntProvider>
  );
}
