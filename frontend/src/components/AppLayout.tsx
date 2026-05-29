import { useRef, useState } from "react";
import { Layout, Input, Menu, Typography, type InputRef } from "antd";
import { SearchOutlined, HomeOutlined, FundOutlined, FilterOutlined, LineChartOutlined, FileTextOutlined, MessageOutlined, SettingOutlined } from "@ant-design/icons";
import { useNavigate, useLocation, Outlet } from "react-router-dom";
import { useStockSearch } from "../api/queries";
import { cardStyle } from "../styles/ui";

const { Header, Content } = Layout;
const { Title } = Typography;

const NAV_ITEMS = [
  { key: "/", icon: <HomeOutlined />, label: "首页" },
  { key: "/market", icon: <FundOutlined />, label: "市场" },
  { key: "/screener", icon: <FilterOutlined />, label: "选股" },
  { key: "/chat", icon: <MessageOutlined />, label: "对话" },
  { key: "/daily-review", icon: <FileTextOutlined />, label: "复盘" },
  { key: "/analysis", icon: <LineChartOutlined />, label: "分析" },
  { key: "/settings", icon: <SettingOutlined />, label: "设置" },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchQuery, setSearchQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const { data: results = [], isFetching } = useStockSearch(searchQuery);
  const searchRef = useRef<InputRef>(null);

  const activeKey = getActiveKey(location.pathname);

  const handleNavClick = (key: string) => {
    navigate(key);
  };

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
    if (e.key === "Escape") {
      setDropdownOpen(false);
    }
  };

  return (
    <Layout style={{ minHeight: "100vh", background: "#0b1120" }}>
      <Header style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 24px", background: "#0f172a",
        borderBottom: "1px solid #1e293b", position: "sticky", top: 0, zIndex: 100,
        boxShadow: "0 1px 4px rgba(0,0,0,0.2)",
      }}>
        {/* Left: Logo + Nav */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: "linear-gradient(135deg, #3b82f6, #6366f1)",
            display: "flex", alignItems: "center", justifyContent: "center",
            marginRight: 8,
          }}>
            <LineChartOutlined style={{ color: "#fff", fontSize: 16 }} />
          </div>
          <Title level={4} style={{ margin: 0, color: "#e5e7eb", whiteSpace: "nowrap", fontSize: 16 }}>
            A股智能分析
          </Title>
          <Menu
            mode="horizontal"
            selectedKeys={[activeKey]}
            items={NAV_ITEMS}
            onClick={({ key }) => handleNavClick(key)}
            style={{ border: "none", marginLeft: 16, fontWeight: 500 }}
          />
        </div>

        {/* Right: Search with Dropdown */}
        <div style={{ position: "relative", maxWidth: 360, width: "100%" }}>
          <Input.Search
            ref={searchRef}
            placeholder="输入股票代码或名称"
            prefix={<SearchOutlined />}
            allowClear
            enterButton
            style={{ width: "100%" }}
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            onSearch={(val) => {
              const trimmed = val.trim();
              if (trimmed.length === 6 && /^\d{6}$/.test(trimmed)) {
                navigate(`/analysis/${trimmed}`);
                setSearchQuery("");
                setDropdownOpen(false);
              } else if (results.length > 0) {
                navigate(`/analysis/${results[0].code}`);
                setSearchQuery("");
                setDropdownOpen(false);
              }
            }}
            onKeyDown={handleKeyDown}
            onFocus={() => { if (searchQuery.length >= 1) setDropdownOpen(true); }}
            onBlur={() => { setTimeout(() => setDropdownOpen(false), 200); }}
          />
          {dropdownOpen && searchQuery.length >= 1 && (
            <div style={{
              ...cardStyle,
              position: "absolute", top: "calc(100% + 8px)", left: 0, right: 0, zIndex: 1000,
              background: "#1a2332",
              maxHeight: 360, overflowY: "auto",
            }}>
              {isFetching && results.length === 0 ? (
                <div style={{ padding: "16px 12px", color: "#9ca3af", fontSize: 13, textAlign: "center" }}>
                  搜索中...
                </div>
              ) : results.length === 0 ? (
                <div style={{ padding: "16px 12px", color: "#9ca3af", fontSize: 13, textAlign: "center" }}>
                  未找到匹配的股票
                </div>
              ) : (
                results.map((item) => (
                  <div
                    key={item.code}
                    onClick={() => handleSelect(item.code)}
                    style={{
                      display: "flex", alignItems: "center", justifyContent: "space-between",
                      padding: "10px 14px", cursor: "pointer",
                      borderBottom: "1px solid #1e293b",
                      transition: "background 0.15s ease",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#1e293b"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ color: "#3b82f6", fontWeight: 600, fontSize: 13, fontFamily: "monospace" }}>
                        {item.code}
                      </span>
                      <span style={{ color: "#e5e7eb", fontSize: 13 }}>{item.name}</span>
                    </div>
                    {item.price != null && (
                      <span style={{
                        fontSize: 12, fontWeight: 500,
                        color: item.change_pct != null
                          ? (item.change_pct > 0 ? "#ef4444" : item.change_pct < 0 ? "#22c55e" : "#9ca3af")
                          : "#9ca3af",
                      }}>
                        {item.price.toFixed(2)}
                        {item.change_pct != null && (
                          <span style={{ marginLeft: 4 }}>
                            {item.change_pct > 0 ? "+" : ""}{item.change_pct.toFixed(2)}%
                          </span>
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

      <Content style={{ padding: "20px 24px" }}>
        <Outlet />
      </Content>
    </Layout>
  );
}

function getActiveKey(pathname: string): string {
  if (pathname === "/") return "/";
  if (pathname.startsWith("/market")) return "/market";
  if (pathname.startsWith("/screener")) return "/screener";
  if (pathname.startsWith("/chat")) return "/chat";
  if (pathname.startsWith("/daily-review")) return "/daily-review";
  if (pathname.startsWith("/analysis")) return "/analysis";
  if (pathname.startsWith("/settings")) return "/settings";
  return "/";
}
