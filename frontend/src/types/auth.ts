export interface AuthUser {
  id: number;
  username: string;
  is_admin: boolean;
  is_active?: boolean;
  must_change_password: boolean;
  created_at?: string | null;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

export interface InviteItem {
  code: string;
  created_by?: number;
  used_by?: number | null;
  used: boolean;
  expired?: boolean;
  created_at?: string | null;
  expires_at?: string | null;
  used_at?: string | null;
}

export interface AdminUserItem {
  id: number;
  username: string;
  is_admin: boolean;
  is_active: boolean;
  must_change_password: boolean;
  created_at?: string | null;
}

export interface LoginAuditLogItem {
  id: number;
  username: string;
  user_id?: number | null;
  ip_address: string;
  user_agent: string;
  status: string;
  details: string;
  created_at: string;
}

export interface SessionItem {
  session_id: string;
  created_at: string;
  expires_at: string;
  ip_address: string;
  user_agent: string;
  /** 最近活跃时间（滑动续期时更新） */
  last_seen_at: string;
  is_current: boolean;
}

export interface SessionsResponse {
  items: SessionItem[];
}

export interface AdminAuditActionItem {
  id: number;
  actor_id?: number | null;
  actor_username: string;
  actor_ip: string;
  actor_user_agent: string;
  action: string;
  target_type: string;
  target_id: string;
  target_label: string;
  details: string;
  created_at: string;
}

export interface AdminAuditActionsResponse {
  items: AdminAuditActionItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface LoginAuditLogsResponse {
  items: LoginAuditLogItem[];
  total: number;
  limit: number;
  offset: number;
}
