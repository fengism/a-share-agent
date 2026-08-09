import { useCallback, useState } from "react";
import { Grid, Layout } from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useColors, useThemeStore } from "../styles/ui";
import AppHeader from "./AppHeader";
import AppSidebar from "./AppSidebar";

const { Content } = Layout;
const { useBreakpoint } = Grid;

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const colors = useColors();
  const themeKey = useThemeStore((state) => state.themeKey);
  const screens = useBreakpoint();
  const isMobile = !screens.md;

  const handleNavigate = useCallback((key: string) => {
    navigate(key);
    setMobileNavOpen(false);
  }, [navigate]);

  return (
    <Layout style={{ minHeight: "100vh", background: colors.pageBg }}>
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
      <Layout style={{ marginLeft: isMobile ? 0 : collapsed ? 64 : 200, transition: "margin-left 0.2s" }}>
        <AppHeader
          isMobile={isMobile}
          themeKey={themeKey}
          onMobileNavOpen={() => setMobileNavOpen(true)}
        />
        <Content style={{ padding: isMobile ? "16px 12px" : "20px 24px", minHeight: "calc(100vh - 56px)" }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}

function getActiveKey(pathname: string): string {
  if (pathname === "/") return "/";
  if (pathname.startsWith("/market")) return "/market";
  if (pathname.startsWith("/macro")) return "/macro";
  if (pathname.startsWith("/compare")) return "/compare";
  if (pathname.startsWith("/portfolio")) return "/portfolio";
  if (pathname.startsWith("/quant")) return "/quant";
  if (pathname.startsWith("/feed")) return "/feed";
  if (pathname.startsWith("/twitter")) return "/twitter";
  if (pathname.startsWith("/screener")) return "/screener";
  if (pathname.startsWith("/chat")) return "/chat";
  if (pathname.startsWith("/daily-review")) return "/daily-review";
  if (pathname.startsWith("/analysis")) return "/analysis";
  if (pathname.startsWith("/industry-chain")) return "/industry-chain";
  if (pathname.startsWith("/capabilities")) return "/capabilities";
  if (pathname.startsWith("/settings")) return "/settings";
  return "/";
}
