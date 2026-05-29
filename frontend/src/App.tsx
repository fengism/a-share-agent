import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import AppLayout from "./components/AppLayout";
import Dashboard from "./pages/Dashboard";
import Market from "./pages/Market";
import Screener from "./pages/Screener";
import Analysis from "./pages/Analysis";
import AnalysisEntry from "./pages/Analysis/Entry";
import DailyReviewPage from "./pages/DailyReview";
import Chat from "./pages/Chat";
import Settings from "./pages/Settings";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: "#3b82f6",
          colorBgContainer: "#111827",
          colorBgElevated: "#1a2332",
          colorBorder: "#1e293b",
          colorText: "#e5e7eb",
          colorTextSecondary: "#9ca3af",
          borderRadius: 10,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        },
      }}
    >
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/market" element={<Market />} />
              <Route path="/screener" element={<Screener />} />
              <Route path="/daily-review" element={<DailyReviewPage />} />
              <Route path="/analysis" element={<AnalysisEntry />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/analysis/:code" element={<Analysis />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ConfigProvider>
  );
}
