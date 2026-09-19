import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useMediaQuery } from "../hooks/useMediaQuery";
import { useColors, useThemeStore } from "../styles/ui";
import AppHeader from "./AppHeader";
import ChatSessionSyncBridge from "./ChatSessionSyncBridge";
import WorkflowRuntimeBridge from "./WorkflowRuntimeBridge";
import AppSidebar from "./AppSidebar";
import RouteLoadingFallback from "./RouteLoadingFallback";
import UpdateBanner from "./UpdateBanner";

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const colors = useColors();
  const themeKey = useThemeStore((state) => state.themeKey);
  const isMobile = useMediaQuery("(max-width: 767px)");
  const contentRef = useRef<HTMLElement>(null);
  const previousPath = useRef(location.pathname);

  useEffect(() => {
    if (previousPath.current === location.pathname) return;
    previousPath.current = location.pathname;
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    contentRef.current?.focus({ preventScroll: true });
  }, [location.pathname]);

  const handleNavigate = useCallback((key: string) => {
    navigate(key);
    setMobileNavOpen(false);
  }, [navigate]);

  return (
    <>
      <ChatSessionSyncBridge />
      <WorkflowRuntimeBridge />
      <a className="app-skip-link" href="#main-content">跳到主要内容</a>
      <div className="app-shell-root" style={{ minHeight: "100vh", backgroundColor: colors.pageBg }}>
        <AppSidebar
          activeKey={getActiveKey(location.pathname)}
          collapsed={collapsed}
          isMobile={isMobile}
          mobileNavOpen={mobileNavOpen}
          themeKey={themeKey}
          onCollapse={setCollapsed}
          onMobileNavClose={() => setMobileNavOpen(false)}
          onNavigate={handleNavigate}
        />
        <div style={{
          display: "flex",
          minWidth: 0,
          minHeight: "100vh",
          flexDirection: "column",
          marginLeft: isMobile ? 0 : collapsed ? 68 : 210,
          transition: "margin-left 0.2s",
        }}>
          <UpdateBanner showIdle={false} />
          <AppHeader
            isMobile={isMobile}
            themeKey={themeKey}
            onMobileNavOpen={() => setMobileNavOpen(true)}
          />
          <main
            id="main-content"
            ref={contentRef}
            tabIndex={-1}
            style={{
              padding: isMobile ? "16px 12px" : "20px 24px",
              minHeight: "calc(100vh - 56px)",
              boxSizing: "border-box",
              flex: "1 1 auto",
            }}
          >
            <Suspense fallback={<RouteLoadingFallback />}>
              <Outlet />
            </Suspense>
          </main>
        </div>
      </div>
    </>
  );
}

function getActiveKey(pathname: string): string {
  if (pathname === "/") return "/";
  if (pathname.startsWith("/watchlist")) return "/watchlist";
  if (pathname.startsWith("/national-team")) return "/national-team";
  if (pathname.startsWith("/market") || pathname.startsWith("/hk-market")) return "/market";
  if (pathname.startsWith("/trading-calendar")) return "/trading-calendar";
  if (pathname.startsWith("/macro")) return "/macro";
  if (pathname.startsWith("/portfolio")) return "/portfolio";
  if (pathname.startsWith("/quant")) return "/quant";
  if (pathname.startsWith("/feed")) return "/feed";
  if (pathname.startsWith("/twitter")) return "/feed";
  if (pathname.startsWith("/screener")) return "/screener";
  if (pathname.startsWith("/chat")) return "/chat";
  if (pathname.startsWith("/daily-review")) return "/daily-review";
  if (pathname.startsWith("/stock")) return "/analysis";
  if (pathname.startsWith("/investment-research")) return "/analysis";
  if (pathname.startsWith("/analysis")) return "/analysis";
  if (pathname.startsWith("/industry-chain")) return "/industry-chain";
  if (pathname.startsWith("/master-data") || pathname.startsWith("/stock-concept") || pathname.startsWith("/industry-classification")) {
    return "/master-data";
  }
  if (pathname.startsWith("/capabilities")) return "/capabilities";
  if (pathname.startsWith("/settings")) return "/settings";
  return "/";
}
