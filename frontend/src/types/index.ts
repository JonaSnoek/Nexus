export interface User {
  id: string | number;
  username: string;
  email: string | null;
  display_name: string | null;
  role: "admin" | "user";
  is_active: boolean;
  is_sso: boolean;
  daily_token_limit: number;
  daily_message_limit: number;
  permissions: string[];
  created_at?: string;
  last_login?: string | null;
}

export interface Permission {
  id: number;
  name: string;
  description: string | null;
}

export interface Chat {
  id: string | number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface Message {
  id: string | number;
  role: "user" | "assistant" | "system";
  content: string;
  tokens: number;
  created_at: string;
}

export interface Usage {
  date: string;
  tokens_used: number;
  messages_used: number;
  token_limit?: number;
  message_limit?: number;
}

export interface AuditLog {
  id: string | number;
  user_id: string | number;
  username?: string;
  action: string;
  resource?: string | null;
  details: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type?: string;
}

export interface HealthResponse {
  status: string;
  database: string;
  ollama: string;
  setup_required: boolean;
  oidc_enabled: boolean;
}

export interface ChatCreate {
  title?: string;
}

export interface ChatUpdate {
  title: string;
}

export interface ChatResponse {
  id: string | number;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
}

export interface SetupRequest {
  username: string;
  display_name: string;
  email: string;
  password: string;
}

export interface UserCreate {
  username: string;
  display_name?: string;
  email?: string;
  password: string;
  role: string;
}

export interface UserUpdate {
  display_name?: string;
  email?: string;
  role?: string;
  is_active?: boolean;
}

export interface DashboardStats {
  users: number;
  active_users: number;
  chats: number;
  messages: number;
  messages_today: number;
  tokens_today: number;
  total_tokens: number;
  date: string;
}

export interface SystemInfo {
  cpu_percent: number | null;
  memory_total: number | null;
  memory_used: number | null;
  memory_percent: number | null;
  disk_total: number | null;
  disk_used: number | null;
  disk_percent: number | null;
  uptime: number | null;
}

export interface ModelInfo {
  name: string;
  size?: number;
  digest?: string;
  modified_at?: string;
}

export interface PullModelRequest {
  model: string;
}

export interface SendMessageRequest {
  content: string;
  model?: string;
}