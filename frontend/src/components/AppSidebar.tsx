import { lazy, Suspense } from "react";
import {
  ApartmentOutlined,
  ApiOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  FilterOutlined,
  FundOutlined,
  GlobalOutlined,
  HomeOutlined,
  LineChartOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MessageOutlined,
  PieChartOutlined,
  ExperimentOutlined,
  SettingOutlined,
  TwitterOutlined,
} from "@ant-design/icons";
import { useColors, useTokens } from "../styles/ui";
import { themes } from "../theme/themes";
import type { ThemeKey } from "../styles/ui";
import { useRoutePreload } from "../routes/RoutePreloadContext";
import { loadMobileSidebarDrawer } from "./mobileSidebarDrawerLoader";

const MobileSidebarDrawer = lazy(loadMobileSidebarDrawer);

const NAV_GROUPS = [
  {
    key: "common",
    label: "常用",
    items: [
      { key: "/", icon: <HomeOutlined />, label: "首页" },
      { key: "/market", icon: <FundOutlined />, label: "市场" },
      { key: "/chat", icon: <MessageOutlined />, label: "对话" },
      { key: "/feed", icon: <ClockCircleOutlined />, label: "资讯" },
    ],
  },
  {
    key: "research",
    label: "研究",
    items: [
      { key: "/analysis", icon: <LineChartOutlined />, label: "个股" },
      { key: "/screener", icon: <FilterOutlined />, label: "选股" },
      { key: "/quant", icon: <ExperimentOutlined />, label: "量化" },
      { key: "/compare", icon: <LineChartOutlined />, label: "对比" },
      { key: "/macro", icon: <GlobalOutlined />, label: "宏观" },
      { key: "/industry-chain", icon: <ApartmentOutlined />, label: "产业链" },
      { key: "/twitter", icon: <TwitterOutlined />, label: "Twitter/X" },
    ],
  },
  {
    key: "management",
    label: "投资管理",
    items: [
      { key: "/portfolio", icon: <PieChartOutlined />, label: "仓位" },
      { key: "/daily-review", icon: <FileTextOutlined />, label: "复盘" },
    ],
  },
  {
    key: "system",
    label: "系统",
    items: [
      { key: "/capabilities", icon: <ApiOutlined />, label: "能力" },
      { key: "/settings", icon: <SettingOutlined />, label: "设置" },
    ],
  },
];

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
    const renderRoute = (item: (typeof NAV_GROUPS)[number]["items"][number]) => (
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

    return (
      <>
        <div className="app-sidebar-brand" style={{ borderBottomColor: colors.border }}>
          {isCollapsed ? (
            <button
              type="button"
              aria-label="展开侧边栏"
              className="al-collapse-btn app-sidebar-brand__expand"
              onClick={() => onCollapse(false)}
            >
              <MenuUnfoldOutlined />
            </button>
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
                <span className="app-sidebar-brand__title" style={{ color: colors.textPrimary, fontSize: t.font.lg }}>
                  A股智能分析
                </span>
              </button>
              {!isMobile && (
                <button
                  type="button"
                  aria-label="收起侧边栏"
                  className="al-collapse-btn app-sidebar-brand__collapse"
                  onClick={() => onCollapse(true)}
                >
                  <MenuFoldOutlined />
                </button>
              )}
            </>
          )}
        </div>

        <nav className={`app-sidebar-nav${isCollapsed ? " app-sidebar-nav--collapsed" : ""}`} aria-label="主导航">
          {isCollapsed
            ? NAV_GROUPS.flatMap((group) => group.items).map(renderRoute)
            : NAV_GROUPS.map((group) => (
                <div className="app-sidebar-nav__group" key={group.key}>
                  <div className="app-sidebar-nav__group-title">{group.label}</div>
                  {group.items.map(renderRoute)}
                </div>
              ))}
        </nav>
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
      style={{
        width: collapsed ? 68 : 184,
        minWidth: collapsed ? 68 : 184,
        maxWidth: collapsed ? 68 : 184,
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
