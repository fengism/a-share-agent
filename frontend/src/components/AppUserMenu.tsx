import { useCallback, useId, useState } from "react";
import { ApiOutlined, LogoutOutlined, SettingOutlined, UserOutlined } from "@ant-design/icons";
import type { AuthUser } from "../types/auth";
import { useDismissibleLayer } from "../hooks/useDismissibleLayer";

interface AppUserMenuProps {
  user: AuthUser;
  isMobile: boolean;
  onCapabilities?: () => void;
  onSettings: () => void;
  onLogout: () => void | Promise<void>;
}

export default function AppUserMenu({
  user,
  isMobile,
  onCapabilities,
  onSettings,
  onLogout,
}: AppUserMenuProps) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const dismiss = useCallback(() => setOpen(false), []);
  const { containerRef, triggerRef } = useDismissibleLayer(open, dismiss);

  const handleCapabilities = () => {
    setOpen(false);
    onCapabilities?.();
  };

  const handleSettings = () => {
    setOpen(false);
    onSettings();
  };

  const handleLogout = () => {
    setOpen(false);
    void onLogout();
  };

  return (
    <div ref={containerRef} className="app-user-menu">
      <button
        ref={triggerRef}
        type="button"
        aria-label="用户菜单"
        aria-controls={open ? menuId : undefined}
        aria-expanded={open}
        aria-haspopup="menu"
        className={`app-user-menu__trigger${isMobile ? " app-user-menu__trigger--mobile" : ""}`}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="app-user-menu__avatar" aria-hidden="true">
          <UserOutlined />
        </span>
        {!isMobile && <span className="app-user-menu__username">{user.username}</span>}
      </button>
      {open && (
        <div id={menuId} className="app-user-menu__panel" role="menu" aria-label="账户操作">
          <div className="app-user-menu__identity">
            <span className="app-user-menu__identity-name">{user.username}</span>
            {user.is_admin && <span className="app-user-menu__admin-badge">管理员</span>}
          </div>
          <div className="app-user-menu__separator" />
          <button type="button" role="menuitem" className="app-user-menu__item" onClick={handleSettings}>
            <SettingOutlined aria-hidden="true" />
            <span>系统设置</span>
          </button>
          {onCapabilities && (
            <button type="button" role="menuitem" className="app-user-menu__item" onClick={handleCapabilities}>
              <ApiOutlined aria-hidden="true" />
              <span>系统能力</span>
            </button>
          )}
          <div className="app-user-menu__separator" />
          <button type="button" role="menuitem" className="app-user-menu__item" onClick={handleLogout}>
            <LogoutOutlined aria-hidden="true" />
            <span>退出登录</span>
          </button>
        </div>
      )}
    </div>
  );
}
