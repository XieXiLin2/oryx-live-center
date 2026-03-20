// ---- User ----
export interface User {
  id: number;
  username: string;
  display_name: string;
  email: string;
  avatar_url: string;
  is_admin: boolean;
  created_at: string;
}

// ---- Auth ----
export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface AuthURLResponse {
  authorize_url: string;
}

// ---- Chat ----
export interface ChatMessage {
  id: number;
  user_id: number;
  username: string;
  display_name: string;
  content: string;
  stream_name: string;
  created_at: string;
}

export interface WsMessage {
  type: 'message' | 'system' | 'error';
  id?: number;
  user_id?: number;
  username?: string;
  display_name?: string;
  avatar_url?: string;
  content: string;
  created_at?: string;
  is_admin?: boolean;
  online_count?: number;
}

// ---- Stream ----
export interface StreamInfo {
  name: string;
  display_name: string;
  app: string;
  video_codec: string | null;
  audio_codec: string | null;
  clients: number;
  is_encrypted: boolean;
  require_auth: boolean;
  formats: string[];
}

export interface StreamPlayResponse {
  url: string;
  stream_name: string;
  format: string;
}

export interface StreamConfig {
  id: number;
  stream_name: string;
  display_name: string;
  is_encrypted: boolean;
  require_auth: boolean;
  created_at: string;
  updated_at: string;
}

// ---- Admin ----
export interface UserListResponse {
  users: User[];
  total: number;
}

export interface ChatHistoryResponse {
  messages: ChatMessage[];
  total: number;
}
