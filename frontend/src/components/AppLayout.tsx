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
import { getActiveNavKey } from "./navConfig";

const SIDEBAR_COLLAPSED_KEY = "trade_agent_sidebar_collapsed";

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
    } catch {
      return false;
    }
  });
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const colors = useColors();
  const themeKey = useThemeStore((state) => state.themeKey);
  const isMobile = useMediaQuery("(max-width: 767px)");
  const contentRef = useRef<HTMLElement>(null);
  const previousPath = useRef(location.pathname);

  const handleCollapse = useCallback((nextCollapsed: boolean) => {
    setCollapsed(nextCollapsed);
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(nextCollapsed));
    } catch {
      // Ignore storage errors
    }
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "b") {
        const activeEl = document.activeElement;
        const isInput =
          activeEl instanceof HTMLInputElement ||
          activeEl instanceof HTMLTextAreaElement ||
          (activeEl as HTMLElement)?.isContentEditable;
        if (!isInput && !isMobile) {
          e.preventDefault();
          setCollapsed((prev) => {
            const next = !prev;
            try {
              localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
            } catch {
              // Ignore storage errors
            }
            return next;
          });
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isMobile]);

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
          activeKey={getActiveNavKey(location.pathname)}
          collapsed={collapsed}
          isMobile={isMobile}
          mobileNavOpen={mobileNavOpen}
          themeKey={themeKey}
          onCollapse={handleCollapse}
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
