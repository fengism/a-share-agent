"""Auth 模块对其他模块开放的稳定入口。"""

from app.contracts.auth import AuthenticatedUser
from app.modules.auth.dependencies import require_active_user, require_admin, require_metrics_access

__all__ = ["AuthenticatedUser", "require_active_user", "require_admin", "require_metrics_access"]
