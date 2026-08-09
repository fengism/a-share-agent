import { Drawer, Layout, Menu, Typography } from "antd";
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
import { useColors } from "../styles/ui";
import { themes } from "../theme/themes";
import type { ThemeKey } from "../styles/ui";

const { Sider } = Layout;
const { Title } = Typography;

const NAV_GROUPS = [
  {
    key: "common",
    label: "常用",
    items: [
      { key: "/", icon: <HomeOutlined />, label: "首页" },
      { key: "/chat", icon: <MessageOutlined />, label: "对话" },
      { key: "/market", icon: <FundOutlined />, label: "市场" },
      { key: "/feed", icon: <ClockCircleOutlined />, label: "资讯" },
    ],
  },
  {
    key: "research",
    label: "研究",
    items: [
      { key: "/analysis", icon: <LineChartOutlined />, label: "分析" },
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
  const colors = useColors();

  const renderContent = (isCollapsed: boolean) => {
    const navItems = isCollapsed
      ? NAV_GROUPS.flatMap((group) => group.items)
      : NAV_GROUPS.map((group) => ({
          key: group.key,
          type: "group" as const,
          label: group.label,
          children: group.items,
        }));

    return (
      <>
      <div style={{
        display: "flex",
        alignItems: "center",
        height: 56,
        borderBottom: `1px solid ${colors.border}`,
      }}>
        {isCollapsed ? (
          <button
            type="button"
            aria-label="展开侧边栏"
            className="al-collapse-btn"
            onClick={() => onCollapse(false)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "100%",
              height: "100%",
              border: 0,
              background: "transparent",
              cursor: "pointer",
              fontSize: 17,
            }}
          >
            <MenuUnfoldOutlined />
          </button>
        ) : (
          <>
            <button
              type="button"
              aria-label="返回首页"
              onClick={() => onNavigate("/")}
              style={{
                display: "flex",
                alignItems: "center",
                flex: 1,
                minWidth: 0,
                gap: 10,
                padding: "0 8px 0 18px",
                border: 0,
                background: "transparent",
                cursor: "pointer",
                font: "inherit",
                textAlign: "left",
              }}
            >
              <span style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                flexShrink: 0,
                background: colors.logoGradient,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}>
                <LineChartOutlined style={{ color: "#fff", fontSize: 16 }} />
              </span>
              <Title level={4} style={{ margin: 0, color: colors.textPrimary, whiteSpace: "nowrap", fontSize: 15 }}>
                A股智能分析
              </Title>
            </button>
            {!isMobile && (
              <button
                type="button"
                aria-label="收起侧边栏"
                className="al-collapse-btn"
                onClick={() => onCollapse(true)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 34,
                  height: 34,
                  marginRight: 8,
                  border: 0,
                  borderRadius: 8,
                  background: "transparent",
                  cursor: "pointer",
                  fontSize: 16,
                  flexShrink: 0,
                }}
              >
                <MenuFoldOutlined />
              </button>
            )}
          </>
        )}
      </div>

      <Menu
        className="app-sidebar-menu"
        mode="inline"
        selectedKeys={[activeKey]}
        items={navItems}
        onClick={({ key }) => onNavigate(key)}
        style={{
          border: "none",
          background: "transparent",
          flex: 1,
          minHeight: 0,
          marginTop: 4,
          overflowY: "auto",
          overflowX: "hidden",
        }}
      />
      </>
    );
  };

  if (isMobile) {
    return (
      <Drawer
        placement="left"
        open={mobileNavOpen}
        onClose={onMobileNavClose}
        width={240}
        closable={false}
        styles={{
          body: {
            padding: 0,
            display: "flex",
            flexDirection: "column",
            background: themes[themeKey].siderBg,
          },
          header: { display: "none" },
        }}
      >
        {renderContent(false)}
      </Drawer>
    );
  }

  return (
    <Sider
      collapsible
      collapsed={collapsed}
      onCollapse={onCollapse}
      width={200}
      collapsedWidth={64}
      style={{
        background: themes[themeKey].siderBg,
        borderRight: `1px solid ${colors.border}`,
        position: "fixed",
        left: 0,
        top: 0,
        bottom: 0,
        zIndex: 110,
        display: "flex",
        flexDirection: "column",
      }}
      trigger={null}
    >
      {renderContent(collapsed)}
    </Sider>
  );
}
