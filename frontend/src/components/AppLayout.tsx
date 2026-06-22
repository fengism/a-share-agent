import { useRef, useState } from "react";
import { Layout, Input, Menu, Typography, Tooltip, type InputRef } from "antd";
import {
  SearchOutlined, HomeOutlined, FundOutlined, FilterOutlined,
  LineChartOutlined, FileTextOutlined, MessageOutlined, SettingOutlined,
  ClockCircleOutlined, ApartmentOutlined, GlobalOutlined,
  BgColorsOutlined,
} from "@ant-design/icons";
import { useNavigate, useLocation, Outlet } from "react-router-dom";
import { useStockSearch } from "../api/queries";
import { useColors, useStyles, useThemeStore, THEME_LIST } from "../styles/ui";
import { themes } from "../theme/themes";
import type { ThemeKey } from "../styles/ui";

const { Header, Sider, Content } = Layout;
const { Title } = Typography;

const NAV_ITEMS = [
  { key: "/", icon: <HomeOutlined />, label: "首页" },
  { key: "/market", icon: <FundOutlined />, label: "市场" },
  { key: "/macro", icon: <GlobalOutlined />, label: "宏观" },
  { key: "/compare", icon: <LineChartOutlined />, label: "对比" },
  { key: "/feed", icon: <ClockCircleOutlined />, label: "资讯" },
  { key: "/screener", icon: <FilterOutlined />, label: "选股" },
  { key: "/chat", icon: <MessageOutlined />, label: "对话" },
  { key: "/daily-review", icon: <FileTextOutlined />, label: "复盘" },
  { key: "/analysis", icon: <LineChartOutlined />, label: "分析" },
  { key: "/industry-chain", icon: <ApartmentOutlined />, label: "产业链" },
  { key: "/settings", icon: <SettingOutlined />, label: "设置" },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchQuery, setSearchQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const { data: results = [], isFetching } = useStockSearch(searchQuery);
  const searchRef = useRef<InputRef>(null);

  const c = useColors();
  const s = useStyles();
  const themeKey = useThemeStore((st) => st.themeKey);
  const setThemeKey = useThemeStore((st) => st.setThemeKey);

  const activeKey = getActiveKey(location.pathname);

  const handleNavClick = (key: string) => navigate(key);

  const handleSearchChange = (val: string) => {
    setSearchQuery(val.trim());
    setDropdownOpen(val.trim().length >= 1);
  };

  const handleSelect = (code: string) => {
    navigate(`/analysis/${code}`);
    setSearchQuery("");
    setDropdownOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      if (searchQuery.length === 6 && /^\d{6}$/.test(searchQuery)) {
        navigate(`/analysis/${searchQuery}`);
        setSearchQuery("");
        setDropdownOpen(false);
      } else if (results.length > 0) {
        navigate(`/analysis/${results[0].code}`);
        setSearchQuery("");
        setDropdownOpen(false);
      }
    }
    if (e.key === "Escape") setDropdownOpen(false);
  };

  const cycleTheme = () => {
    const keys = THEME_LIST.map((t) => t.key);
    const idx = keys.indexOf(themeKey);
    setThemeKey(keys[(idx + 1) % keys.length] as ThemeKey);
  };

  return (
    <Layout style={{ minHeight: "100vh", background: c.pageBg }}>
      {/* Sidebar */}
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        width={200}
        collapsedWidth={64}
        style={{
          background: themes[themeKey].siderBg,
          borderRight: `1px solid ${c.border}`,
          position: "fixed",
          left: 0, top: 0, bottom: 0,
          zIndex: 110,
          display: "flex",
          flexDirection: "column",
        }}
        trigger={null}
      >
        {/* Logo */}
        <div
          style={{
            display: "flex", alignItems: "center",
            justifyContent: collapsed ? "center" : "flex-start",
            gap: 10,
            padding: collapsed ? "16px 0" : "16px 18px",
            borderBottom: `1px solid ${c.border}`,
            height: 56, cursor: "pointer",
          }}
          onClick={() => navigate("/")}
        >
          <div style={{
            width: 32, height: 32, borderRadius: 8, flexShrink: 0,
            background: c.logoGradient,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <LineChartOutlined style={{ color: "#fff", fontSize: 16 }} />
          </div>
          {!collapsed && (
            <Title level={4} style={{ margin: 0, color: c.textPrimary, whiteSpace: "nowrap", fontSize: 15 }}>
              A股智能分析
            </Title>
          )}
        </div>

        {/* Nav Menu */}
        <Menu
          mode="inline"
          selectedKeys={[activeKey]}
          items={NAV_ITEMS}
          onClick={({ key }) => handleNavClick(key)}
          style={{ border: "none", background: "transparent", flex: 1, marginTop: 4 }}
        />

        {/* Bottom actions */}
        <div style={{
          borderTop: `1px solid ${c.border}`,
          display: "flex", flexDirection: "column", alignItems: "center",
          padding: "8px 0", gap: 4,
        }}>
          {/* Theme switcher */}
          <Tooltip title={`切换主题：${THEME_LIST.find((t) => t.key === themeKey)?.label}`} placement="right">
            <div
              onClick={cycleTheme}
              style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                width: 36, height: 36, borderRadius: 8, cursor: "pointer",
                background: c.elevatedBg, border: `1px solid ${c.border}`,
                transition: "border-color 0.2s",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = c.primary; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = c.border; }}
            >
              <BgColorsOutlined style={{ color: c.primary, fontSize: 16 }} />
            </div>
          </Tooltip>

          {/* Collapse toggle */}
          <div
            onClick={() => setCollapsed(!collapsed)}
            style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              width: 36, height: 36, borderRadius: 8, cursor: "pointer",
              color: c.textSecondary, fontSize: 14, transition: "color 0.2s",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = c.textPrimary; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = c.textSecondary; }}
          >
            {collapsed ? "»" : "«"}
          </div>
        </div>
      </Sider>

      {/* Main area */}
      <Layout style={{ marginLeft: collapsed ? 64 : 200, transition: "margin-left 0.2s" }}>
        <Header style={{
          display: "flex", alignItems: "center", justifyContent: "flex-end",
          padding: "0 24px", background: themes[themeKey].headerBg,
          borderBottom: `1px solid ${c.border}`,
          position: "sticky", top: 0, zIndex: 100,
          boxShadow: "0 1px 4px rgba(0,0,0,0.2)", height: 56,
        }}>
          <div style={{ position: "relative", maxWidth: 400, width: "100%" }}>
            <Input.Search
              ref={searchRef}
              placeholder="输入股票代码或名称"
              prefix={<SearchOutlined />}
              allowClear enterButton
              style={{ width: "100%" }}
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              onSearch={(val) => {
                const trimmed = val.trim();
                if (trimmed.length === 6 && /^\d{6}$/.test(trimmed)) {
                  navigate(`/analysis/${trimmed}`);
                  setSearchQuery(""); setDropdownOpen(false);
                } else if (results.length > 0) {
                  navigate(`/analysis/${results[0].code}`);
                  setSearchQuery(""); setDropdownOpen(false);
                }
              }}
              onKeyDown={handleKeyDown}
              onFocus={() => { if (searchQuery.length >= 1) setDropdownOpen(true); }}
              onBlur={() => { setTimeout(() => setDropdownOpen(false), 200); }}
            />
            {dropdownOpen && searchQuery.length >= 1 && (
              <div style={{
                ...s.cardStyle,
                position: "absolute", top: "calc(100% + 8px)", left: 0, right: 0, zIndex: 1000,
                background: c.elevatedBg, maxHeight: 360, overflowY: "auto",
              }}>
                {isFetching && results.length === 0 ? (
                  <div style={{ padding: "16px 12px", color: c.textSecondary, fontSize: 13, textAlign: "center" }}>搜索中...</div>
                ) : results.length === 0 ? (
                  <div style={{ padding: "16px 12px", color: c.textSecondary, fontSize: 13, textAlign: "center" }}>未找到匹配的股票</div>
                ) : (
                  results.map((item) => (
                    <div
                      key={item.code}
                      onClick={() => handleSelect(item.code)}
                      style={{
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        padding: "10px 14px", cursor: "pointer",
                        borderBottom: `1px solid ${c.border}`, transition: "background 0.15s ease",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = c.cardBg; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ color: c.primary, fontWeight: 600, fontSize: 13, fontFamily: "monospace" }}>{item.code}</span>
                        <span style={{ color: c.textPrimary, fontSize: 13 }}>{item.name}</span>
                      </div>
                      {item.price != null && (
                        <span style={{
                          fontSize: 12, fontWeight: 500,
                          color: item.change_pct != null
                            ? (item.change_pct > 0 ? c.up : item.change_pct < 0 ? c.down : c.textSecondary)
                            : c.textSecondary,
                        }}>
                          {item.price.toFixed(2)}
                          {item.change_pct != null && (
                            <span style={{ marginLeft: 4 }}>{item.change_pct > 0 ? "+" : ""}{item.change_pct.toFixed(2)}%</span>
                          )}
                        </span>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </Header>

        <Content style={{ padding: "20px 24px", minHeight: "calc(100vh - 56px)" }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}

function getActiveKey(pathname: string): string {
  if (pathname === "/") return "/";
  if (pathname.startsWith("/market")) return "/market";
  if (pathname.startsWith("/feed")) return "/feed";
  if (pathname.startsWith("/screener")) return "/screener";
  if (pathname.startsWith("/chat")) return "/chat";
  if (pathname.startsWith("/daily-review")) return "/daily-review";
  if (pathname.startsWith("/analysis")) return "/analysis";
  if (pathname.startsWith("/macro")) return "/macro";
  if (pathname.startsWith("/industry-chain")) return "/industry-chain";
  if (pathname.startsWith("/settings")) return "/settings";
  return "/";
}
