import { useCallback, useMemo } from "react";
import { AutoComplete, Avatar, Button, Dropdown, Input, Layout, Tag } from "antd";
import {
  LogoutOutlined,
  MenuOutlined,
  SearchOutlined,
  SettingOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useStockSearchController } from "../hooks/useStockSearchController";
import { useAuthStore } from "../store/authStore";
import { useColors } from "../styles/ui";
import { themes } from "../theme/themes";
import QueryErrorState from "./QueryErrorState";
import ThemeSelector from "./ThemeSelector";
import type { ThemeKey } from "../styles/ui";

const { Header } = Layout;

interface AppHeaderProps {
  isMobile: boolean;
  themeKey: ThemeKey;
  onMobileNavOpen: () => void;
}

export default function AppHeader({ isMobile, themeKey, onMobileNavOpen }: AppHeaderProps) {
  const navigate = useNavigate();
  const {
    inputValue,
    normalizedInput,
    currentResults,
    isPending,
    isError,
    error,
    retry,
    setInputValue,
    clear,
    resolveCode,
  } = useStockSearchController();
  const colors = useColors();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const searchOptions = useMemo(() => currentResults.map((item) => ({
    value: item.code,
    label: (
      <span style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <span style={{ color: colors.primary, fontWeight: 600, fontSize: 13, fontFamily: "monospace" }}>{item.code}</span>
          <span style={{ color: colors.textPrimary, fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {item.name}
          </span>
        </span>
        {!isMobile && item.price != null && (
          <span style={{
            fontSize: 12,
            fontWeight: 500,
            flexShrink: 0,
            color: item.change_pct != null
              ? (item.change_pct > 0 ? colors.up : item.change_pct < 0 ? colors.down : colors.textSecondary)
              : colors.textSecondary,
          }}>
            {item.price.toFixed(2)}
            {item.change_pct != null && (
              <span style={{ marginLeft: 4 }}>{item.change_pct > 0 ? "+" : ""}{item.change_pct.toFixed(2)}%</span>
            )}
          </span>
        )}
      </span>
    ),
  })), [colors, currentResults, isMobile]);

  const handleLogout = useCallback(async () => {
    await logout();
    navigate("/login", { replace: true });
  }, [logout, navigate]);

  const handleSelect = useCallback((code: string) => {
    navigate(`/analysis/${code}`);
    clear();
  }, [clear, navigate]);

  const handleSearchSubmit = useCallback((value: string) => {
    const code = resolveCode(value);
    if (code) handleSelect(code);
  }, [handleSelect, resolveCode]);

  return (
    <Header style={{
      display: "flex",
      alignItems: "center",
      gap: isMobile ? 8 : 12,
      padding: isMobile ? "0 8px" : "0 24px",
      background: themes[themeKey].headerBg,
      borderBottom: `1px solid ${colors.border}`,
      position: "sticky",
      top: 0,
      zIndex: 100,
      boxShadow: "0 1px 4px rgba(0,0,0,0.2)",
      height: 56,
      lineHeight: "normal",
    }}>
      {isMobile && (
        <Button
          type="text"
          aria-label="打开导航菜单"
          icon={<MenuOutlined style={{ fontSize: 18 }} />}
          onClick={onMobileNavOpen}
          style={{ color: colors.textPrimary, flexShrink: 0, width: 40, height: 40, padding: 0 }}
        />
      )}
      <div style={{
        position: "relative",
        flex: isMobile ? "1 1 0" : "0 1 400px",
        minWidth: 0,
        maxWidth: 400,
        width: "100%",
        height: 40,
        marginLeft: "auto",
      }}>
        <AutoComplete
          style={{ width: "100%", height: 40 }}
          value={inputValue}
          options={searchOptions}
          onChange={setInputValue}
          onSelect={handleSelect}
          filterOption={false}
          notFoundContent={
            isPending
              ? "搜索中..."
              : isError
                ? <QueryErrorState error={error} onRetry={() => retry()} title="搜索失败" compact />
                : normalizedInput ? "未找到匹配的股票" : null
          }
        >
          <Input.Search
            className="app-header-search"
            size="large"
            placeholder={isMobile ? "代码 / 名称" : "输入股票代码或名称"}
            prefix={isMobile ? undefined : <SearchOutlined />}
            allowClear
            enterButton
            onSearch={handleSearchSubmit}
            aria-label="搜索股票"
            aria-busy={isPending}
          />
        </AutoComplete>
      </div>

      <ThemeSelector iconOnly />

      {user && (
        <Dropdown
          trigger={["click"]}
          menu={{
            items: [
              {
                key: "user",
                disabled: true,
                label: (
                  <span style={{ fontWeight: 600 }}>
                    {user.username}
                    {user.is_admin && <Tag color="gold" style={{ marginLeft: 6 }}>管理员</Tag>}
                  </span>
                ),
              },
              { type: "divider" },
              { key: "settings", icon: <SettingOutlined />, label: "设置", onClick: () => navigate("/settings") },
              { key: "logout", icon: <LogoutOutlined />, label: "退出登录", onClick: handleLogout },
            ],
          }}
        >
          <button
            type="button"
            aria-label="用户菜单"
            className="al-icon-btn"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: isMobile ? 0 : 8,
              cursor: "pointer",
              width: isMobile ? 40 : undefined,
              padding: isMobile ? 0 : "4px 8px",
              borderRadius: 8,
              flexShrink: 0,
              background: "transparent",
              font: "inherit",
              lineHeight: 1,
              height: 40,
              boxSizing: "border-box",
            }}
          >
            <Avatar size={30} style={{ background: colors.primary }} icon={<UserOutlined />} />
            {!isMobile && (
              <span style={{
                color: colors.textPrimary,
                fontSize: 13,
                maxWidth: 120,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}>
                {user.username}
              </span>
            )}
          </button>
        </Dropdown>
      )}
    </Header>
  );
}
