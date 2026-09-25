import { lazy, Suspense } from "react";
import {
  LineChartOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from "@ant-design/icons";
import { Tooltip } from "antd";
import { useColors, useTokens } from "../styles/ui";
import { themes } from "../theme/themes";
import type { ThemeKey } from "../styles/ui";
import { useRoutePreload } from "../routes/RoutePreloadContext";
import { loadMobileSidebarDrawer } from "./mobileSidebarDrawerLoader";
import { NAV_GROUPS } from "./navConfig";
import type { NavItemConfig } from "./navConfig";

const MobileSidebarDrawer = lazy(loadMobileSidebarDrawer);

interface AppSidebarProps {
  activeKey: string;
  collapsed: boolean;
  isMobile: boolean;
  mobileNavOpen: boolean;
  themeKey: ThemeKey;
  onCollapse: (collapsed: boolean) => void;
  onMobileNavClose: () => void;
  onNavigate: (key: string) => void;
}

export default function AppSidebar({
  activeKey,
  collapsed,
  isMobile,
  mobileNavOpen,
  themeKey,
  onCollapse,
  onMobileNavClose,
  onNavigate,
}: AppSidebarProps) {
  const preloadAppRoute = useRoutePreload();
  const colors = useColors();
  const t = useTokens();

  const renderContent = (isCollapsed: boolean) => {
    const renderRoute = (item: NavItemConfig) => {
      const button = (
        <button
          key={item.key}
          type="button"
          className="app-sidebar-nav__item"
          aria-current={activeKey === item.key ? "page" : undefined}
          aria-label={isCollapsed ? item.label : undefined}
          title={isCollapsed ? item.label : undefined}
          onPointerEnter={() => void preloadAppRoute(item.key)}
          onFocus={() => void preloadAppRoute(item.key)}
          onClick={() => onNavigate(item.key)}
        >
          <span className="app-sidebar-nav__icon" aria-hidden="true">{item.icon}</span>
          {!isCollapsed && <span className="app-sidebar-nav__label">{item.label}</span>}
        </button>
      );

      if (isCollapsed) {
        return (
          <Tooltip
            key={item.key}
            placement="right"
            title={item.label}
            mouseEnterDelay={0.12}
            destroyOnHidden
          >
            {button}
          </Tooltip>
        );
      }

      return button;
    };

    return (
      <>
        <div className="app-sidebar-brand" style={{ borderBottomColor: colors.border }}>
          {isCollapsed ? (
            <Tooltip placement="right" title="展开侧边栏 (⌘B / Ctrl+B)" mouseEnterDelay={0.3}>
              <button
                type="button"
                aria-label="展开侧边栏"
                className="al-collapse-btn app-sidebar-brand__expand"
                onClick={() => onCollapse(false)}
              >
                <MenuUnfoldOutlined />
              </button>
            </Tooltip>
          ) : (
            <>
              <button
                type="button"
                aria-label="返回首页"
                className="app-sidebar-brand__home"
                onPointerEnter={() => void preloadAppRoute("/")}
                onFocus={() => void preloadAppRoute("/")}
                onClick={() => onNavigate("/")}
              >
                <span
                  className="app-sidebar-brand__logo"
                  style={{ borderRadius: t.radius.md, background: colors.logoGradient }}
                >
                  <LineChartOutlined style={{ color: colors.onPrimary, fontSize: 16 }} />
                </span>
                <div className="app-sidebar-brand__text">
                  <span className="app-sidebar-brand__title" style={{ color: colors.textPrimary, fontSize: t.font.lg }}>
                    智能投研平台
                  </span>
                  <span className="app-sidebar-brand__tag">QUANT TERMINAL</span>
                </div>
              </button>
              {!isMobile && (
                <Tooltip placement="bottom" title="收起侧边栏 (⌘B / Ctrl+B)" mouseEnterDelay={0.3}>
                  <button
                    type="button"
                    aria-label="收起侧边栏"
                    className="al-collapse-btn app-sidebar-brand__collapse"
                    onClick={() => onCollapse(true)}
                  >
                    <MenuFoldOutlined />
                  </button>
                </Tooltip>
              )}
            </>
          )}
        </div>

        <nav className={`app-sidebar-nav${isCollapsed ? " app-sidebar-nav--collapsed" : ""}`} aria-label="主导航">
          {isCollapsed
            ? NAV_GROUPS.map((group, groupIdx) => (
                <div key={group.key} className="app-sidebar-nav__collapsed-group">
                  {groupIdx > 0 && <div className="app-sidebar-nav__divider" aria-hidden="true" />}
                  {group.items.map(renderRoute)}
                </div>
              ))
            : NAV_GROUPS.map((group) => (
                <div className="app-sidebar-nav__group" key={group.key}>
                  <div className="app-sidebar-nav__group-title">
                    {group.icon && <span style={{ marginRight: 6, fontSize: 11, opacity: 0.85 }}>{group.icon}</span>}
                    {group.label}
                  </div>
                  {group.items.map(renderRoute)}
                </div>
              ))}
        </nav>

        <div className={`app-sidebar-footer${isCollapsed ? " app-sidebar-footer--collapsed" : ""}`}>
          <Tooltip
            placement="right"
            title={isCollapsed ? "量化雷达: 在线 (⌘B / Ctrl+B 展开)" : "量化雷达: 核心行情服务在线"}
            mouseEnterDelay={0.3}
          >
            <div className="app-sidebar-footer__status" title="QUANT RADAR: 在线">
              <span className="app-sidebar-footer__pulse" />
              {!isCollapsed && (
                <>
                  <span className="app-sidebar-footer__label">QUANT RADAR</span>
                  <span className="app-sidebar-footer__badge">ONLINE</span>
                </>
              )}
            </div>
          </Tooltip>
        </div>
      </>
    );
  };

  if (isMobile) {
    return (
      <Suspense fallback={null}>
        <MobileSidebarDrawer
          open={mobileNavOpen}
          onClose={onMobileNavClose}
          themeKey={themeKey}
        >
          {renderContent(false)}
        </MobileSidebarDrawer>
      </Suspense>
    );
  }

  return (
    <aside
      aria-label="应用侧栏"
      className="app-sidebar-aside"
      style={{
        width: collapsed ? 68 : 210,
        minWidth: collapsed ? 68 : 210,
        maxWidth: collapsed ? 68 : 210,
        background: themes[themeKey].siderBg,
        borderRight: `1px solid ${colors.border}`,
        position: "fixed",
        left: 0,
        top: 0,
        bottom: 0,
        zIndex: Number(t.z.sidebar),
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        boxSizing: "border-box",
        transition: "width 0.2s, min-width 0.2s, max-width 0.2s",
      }}
    >
      {renderContent(collapsed)}
    </aside>
  );
}
