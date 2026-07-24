import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Spin } from "antd";
import { useAuthStore } from "../store/authStore";
import { useColors } from "../styles/ui";

/**
 * Route guard (used as a layout route). While the persisted token is being
 * validated, shows a spinner; unauthenticated users are redirected to /login,
 * preserving the intended destination in navigation state.
 */
export default function RequireAuth() {
  const user = useAuthStore((s) => s.user);
  const bootstrapped = useAuthStore((s) => s.bootstrapped);
  const location = useLocation();
  const c = useColors();

  if (!bootstrapped) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          gap: 12,
          alignItems: "center",
          justifyContent: "center",
          background: c.pageBg,
        }}
      >
        <Spin size="large" />
        <div style={{ color: c.textSecondary, fontSize: 13 }}>正在验证登录状态...</div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
