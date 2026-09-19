import { useCallback } from "react";
import { MenuOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import { useColors, useTokens } from "../styles/ui";
import { themes } from "../theme/themes";
import DeferredAppHeaderSearch from "./DeferredAppHeaderSearch";
import HeaderMarketTicker from "./HeaderMarketTicker";
import ThemeSelector from "./ThemeSelector";
import AppUserMenu from "./AppUserMenu";
import GlobalTaskIndicator from "./GlobalTaskIndicator";
import type { ThemeKey } from "../styles/ui";

interface AppHeaderProps {
  isMobile: boolean;
  themeKey: ThemeKey;
  onMobileNavOpen: () => void;
}

export default function AppHeader({ isMobile, themeKey, onMobileNavOpen }: AppHeaderProps) {
  const navigate = useNavigate();
  const colors = useColors();
  const t = useTokens();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const handleLogout = useCallback(async () => {
    await logout();
    navigate("/login", { replace: true });
  }, [logout, navigate]);

  return (
    <header
      className="app-command-header"
      style={{
        gap: isMobile ? t.space[2] : t.space[3],
        padding: isMobile ? `0 ${t.space[2]}` : `0 ${t.space[5]}`,
        background: themes[themeKey].headerBg,
        borderBottom: `1px solid ${colors.border}`,
        zIndex: Number(t.z.header),
      }}
    >
      {isMobile && (
        <button
          type="button"
          aria-label="打开导航菜单"
          className="app-header-menu-button"
          onClick={onMobileNavOpen}
          style={{ color: colors.textPrimary, flexShrink: 0, width: 40, height: 40, padding: 0 }}
        >
          <MenuOutlined style={{ fontSize: 18 }} />
        </button>
      )}
      {!isMobile && <HeaderMarketTicker />}
      <div className="app-command-header__search">
        <DeferredAppHeaderSearch isMobile={isMobile} />
      </div>

      <GlobalTaskIndicator compact={isMobile} />
      <ThemeSelector iconOnly />

      {user && (
        <AppUserMenu
          user={user}
          isMobile={isMobile}
          onSettings={() => navigate("/settings")}
          onLogout={handleLogout}
        />
      )}
    </header>
  );
}
