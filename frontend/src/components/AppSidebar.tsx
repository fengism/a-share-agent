import { lazy, Suspense } from "react";
import {
  ApartmentOutlined,
  ApiOutlined,
  AuditOutlined,
  BankOutlined,
  BulbOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  ControlOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  RadarChartOutlined,
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
  StarOutlined,
} from "@ant-design/icons";
import { useColors, useTokens } from "../styles/ui";
import { themes } from "../theme/themes";
import type { ThemeKey } from "../styles/ui";
import { useRoutePreload } from "../routes/RoutePreloadContext";
import { loadMobileSidebarDrawer } from "./mobileSidebarDrawerLoader";

const MobileSidebarDrawer = lazy(loadMobileSidebarDrawer);

const NAV_GROUPS = [
  {
    key: "market",
    label: "行情资讯",
    icon: <DashboardOutlined />,
    items: [
      { key: "/", icon: <HomeOutlined />, label: "首页" },
      { key: "/watchlist", icon: <StarOutlined />, label: "自选" },
      { key: "/market", icon: <FundOutlined />, label: "市场" },
      { key: "/national-team", icon: <BankOutlined />, label: "国家队" },
      { key: "/feed", icon: <ClockCircleOutlined />, label: "资讯" },
    ],
  },
  {
    key: "macro_industry",
    label: "宏观产业",
    icon: <GlobalOutlined />,
    items: [
      { key: "/macro", icon: <GlobalOutlined />, label: "宏观" },
      { key: "/industry-chain", icon: <ApartmentOutlined />, label: "产业链" },
    ],
  },
  {
    key: "research",
    label: "个股投研",
    icon: <BulbOutlined />,
    items: [
      { key: "/chat", icon: <MessageOutlined />, label: "对话" },
      { key: "/analysis", icon: <FileSearchOutlined />, label: "个股" },
      { key: "/screener", icon: <FilterOutlined />, label: "选股" },
      { key: "/potential", icon: <RadarChartOutlined />, label: "潜力股" },
    ],
  },
  {
    key: "trading",
    label: "交易策略",
    icon: <AuditOutlined />,
    items: [
      { key: "/portfolio", icon: <PieChartOutlined />, label: "仓位" },
      { key: "/quant", icon: <ExperimentOutlined />, label: "量化" },
      { key: "/daily-review", icon: <FileTextOutlined />, label: "复盘" },
      { key: "/trading-calendar", icon: <CalendarOutlined />, label: "交易日历" },
    ],
  },
  {
    key: "master_data",
    label: "基础数据",
    icon: <DatabaseOutlined />,
    items: [
      { key: "/master-data", icon: <DatabaseOutlined />, label: "主数据管理" },
    ],
  },
  {
    key: "system",
    label: "系统管理",
    icon: <ControlOutlined />,
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
                <div className="app-sidebar-brand__text">
                  <span className="app-sidebar-brand__title" style={{ color: colors.textPrimary, fontSize: t.font.lg }}>
                    A股智能分析
                  </span>
                  <span className="app-sidebar-brand__tag">QUANT TERMINAL</span>
                </div>
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
                  <div className="app-sidebar-nav__group-title">
                    {group.icon && <span style={{ marginRight: 6, fontSize: 11, opacity: 0.85 }}>{group.icon}</span>}
                    {group.label}
                  </div>
                  {group.items.map(renderRoute)}
                </div>
              ))}
        </nav>

        <div className={`app-sidebar-footer${isCollapsed ? " app-sidebar-footer--collapsed" : ""}`}>
          <div className="app-sidebar-footer__status" title="QUANT RADAR: 在线">
            <span className="app-sidebar-footer__pulse" />
            {!isCollapsed && (
              <>
                <span className="app-sidebar-footer__label">QUANT RADAR</span>
                <span className="app-sidebar-footer__badge">ONLINE</span>
              </>
            )}
          </div>
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
