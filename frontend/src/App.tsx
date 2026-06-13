import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider, Spin, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import { useThemeStore, getAntToken } from "./styles/ui";
import { themes } from "./theme/themes";
import AppLayout from "./components/AppLayout";
import ErrorBoundary from "./components/ErrorBoundary";

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
const Macro = lazy(() => import("./pages/Macro"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

function AntProvider({ children }: { children: React.ReactNode }) {
  const themeKey = useThemeStore((s) => s.themeKey);
  const meta = themes[themeKey];
  const token = getAntToken();

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: meta.isLight ? theme.defaultAlgorithm : theme.darkAlgorithm,
        token: {
          ...token,
          borderRadius: 10,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
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
  return (
    <AntProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ErrorBoundary>
            <Suspense fallback={PageFallback}>
              <Routes>
                <Route element={<AppLayout />}>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/market" element={<Market />} />
                  <Route path="/screener" element={<Screener />} />
                  <Route path="/daily-review" element={<DailyReviewPage />} />
                  <Route path="/feed" element={<Feed />} />
                  <Route path="/analysis" element={<AnalysisEntry />} />
                  <Route path="/macro" element={<Macro />} />
                  <Route path="/industry-chain" element={<IndustryChain />} />
                  <Route path="/industry-chain/:name" element={<IndustryChain />} />
                  <Route path="/chat" element={<Chat />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="/analysis/:code" element={<Analysis />} />
                </Route>
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </BrowserRouter>
      </QueryClientProvider>
    </AntProvider>
  );
}
