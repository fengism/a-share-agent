import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import LoadingSpinner from "./LoadingSpinner";

/**
 * Route guard (used as a layout route). While the persisted token is being
 * validated, shows a spinner; unauthenticated users are redirected to /login,
 * preserving the intended destination in navigation state.
 */
export default function RequireAuth() {
  const user = useAuthStore((s) => s.user);
  const bootstrapped = useAuthStore((s) => s.bootstrapped);
  const location = useLocation();

  if (!bootstrapped) {
    return (
      <div className="app-auth-loading" role="status" aria-live="polite">
        <LoadingSpinner size="large" />
        <div>正在验证登录状态...</div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  // Force a password change (seeded admin / flagged account) before anything else.
  if (user.must_change_password && location.pathname !== "/force-change-password") {
    return <Navigate to="/force-change-password" replace />;
  }
  // Don't linger on the forced-change screen once it's no longer required.
  if (!user.must_change_password && location.pathname === "/force-change-password") {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
