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

export interface LoginAuditLogsResponse {
  items: LoginAuditLogItem[];
  total: number;
  limit: number;
  offset: number;
}
