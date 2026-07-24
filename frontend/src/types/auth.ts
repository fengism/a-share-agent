export interface AuthUser {
  id: number;
  username: string;
  is_admin: boolean;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

export interface InviteItem {
  code: string;
  used: boolean;
  created_at?: string | null;
  expires_at?: string | null;
}
