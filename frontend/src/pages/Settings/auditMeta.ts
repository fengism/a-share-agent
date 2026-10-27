/** 管理员操作审计的展示映射与详情拍平（独立成模块以满足 react-refresh 的「只导组件」约束）。 */

export const ACTION_LABELS: Record<string, string> = {
  "user.status": "启用/禁用账号",
  "user.role": "修改角色",
  "user.delete": "删除用户",
  "user.revoke_sessions": "强制下线",
  "session.revoke": "自助退出设备",
  "user.must_change_password": "强制改密标记",
  "user.reset_link": "签发重置链接",
  "invite.create": "创建邀请码",
  "invite.revoke": "吊销邀请码",
  "invite.cleanup": "清理过期邀请码",
  "config.update_global": "修改全局配置",
};

export const ACTION_FILTERS = Object.entries(ACTION_LABELS).map(([value, label]) => ({
  value,
  label,
}));

/** 登录审计状态的展示映射（tone 对应 semanticTagStyle 的语义色）。 */
export const LOGIN_STATUS_META: Record<
  string,
  { label: string; tone: "down" | "warning" | "up" | "info" }
> = {
  success: { label: "登录成功", tone: "down" },
  failed_credentials: { label: "密码错误", tone: "warning" },
  failed_disabled: { label: "账号已停用", tone: "up" },
  failed_rate_limited: { label: "限流阻断", tone: "info" },
};

export function loginStatusMeta(status: string): { label: string; tone: "down" | "warning" | "up" | "info" } {
  return LOGIN_STATUS_META[status] ?? { label: status, tone: "info" };
}

export const LOGIN_STATUS_FILTERS = Object.entries(LOGIN_STATUS_META).map(([value, meta]) => ({
  value,
  label: meta.label,
}));

/** 把 details 里的 JSON 拍平成一行可读文本；只展示字段名与布尔/数字这类非敏感取值。 */
export function summarizeDetails(details: string): string {
  if (!details) return "—";
  try {
    const parsed = JSON.parse(details) as Record<string, unknown>;
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) return details;
    const parts = Object.entries(parsed).map(([key, value]) => {
      if (Array.isArray(value)) {
        return `${key}: ${
          value.length > 6
            ? `${value.slice(0, 6).join(", ")} 等 ${value.length} 项`
            : value.join(", ")
        }`;
      }
      if (typeof value === "boolean") return `${key}: ${value ? "是" : "否"}`;
      return `${key}: ${String(value)}`;
    });
    return parts.join("；") || "—";
  } catch {
    return details;
  }
}
