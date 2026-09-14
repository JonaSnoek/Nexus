export interface User {
  id: string | number;
  username: string;
  email: string | null;
  display_name: string | null;
  role: "admin" | "user";
  is_active: boolean;
  is_sso: boolean;
  monthly_token_limit: number;
  monthly_message_limit: number;
  period: string;
  tokens_used_month: number;
  messages_used_month: number;
  tokens_remaining_month: number;
  messages_remaining_month: number;
  limits_exempt?: boolean;
  custom_monthly_token_limit?: number | null;
  unlimited?: boolean;
  has_token_limit?: boolean;
  effective_token_limit?: number | null;
  tokens_remaining?: number | null;
  used_percent?: number | null;
  permissions: string[];
  action_counts?: Record<string, number>;
  images_used_month?: number;
  chat_messages_count_month?: number;
  created_at?: string;
  last_login?: string | null;
}

export interface UserLimits {
  user_id: string | number;
  limits_exempt: boolean;
  custom_monthly_token_limit: number | null;
  unlimited: boolean;
  effective_token_limit: number | null;
  has_token_limit: boolean;
  tokens_used: number;
  tokens_remaining: number | null;
  used_percent: number | null;
  monthly_message_limit: number;
  messages_used: number;
}

export interface UsageEvent {
  id: string | number;
  action_type: string;
  tokens: number;
  period: string;
  created_at: string;
  metadata?: string | null;
}

export interface UsageSummaryUser {
  user_id: string | number;
  username: string;
  display_name: string | null;
  role: string;
  limit: number | null;
  unlimited: boolean;
  has_limit: boolean;
  used: number;
  messages: number;
  remaining: number | null;
  used_percent: number | null;
  tokens_today: number;
  actions_today: number;
  actions: Record<string, number>;
}

export interface UsageSummary {
  period: string;
  users: UsageSummaryUser[];
  total_tokens_used: number;
  total_messages: number;
  total_actions: number;
  total_chat_tokens?: number;
  total_image_tokens?: number;
  total_chat_actions?: number;
  total_image_actions?: number;
  default_token_limit: number;
}

export interface LimitErrorDetail {
  error_code?: string;
  action_type?: string;
  cost?: number;
  monthly_limit?: number | null;
  used?: number;
  remaining?: number;
  message?: string;
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
  image_id?: number | null;
  image?: GeneratedImage | null;
}

export interface GeneratedImage {
  id: number;
  user_id: number;
  chat_id: number | null;
  status: string;
  prompt: string;
  provider: string | null;
  model: string | null;
  width: number | null;
  height: number | null;
  bytes_size: number | null;
  seconds: number | null;
  token_cost: number;
  period: string | null;
  error: string | null;
  created_at: string | null;
  url: string;
}

export interface ImageGenerateRequest {
  prompt: string;
  chat_id?: number | null;
  model?: string | null;
  size?: string | null;
}

export interface ImageProviderSettings {
  image_provider: string;
  image_model: string;
  image_api_url: string;
  has_api_key: boolean;
  api_key_tail: string;
  configured: boolean;
}

export interface ImageProviderSettingsUpdate {
  image_provider?: string | null;
  image_model?: string | null;
  image_api_url?: string | null;
  image_api_key?: string | null;
}

export interface Usage {
  period: string;
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
  monthly_token_limit?: number;
  monthly_message_limit?: number;
}

export interface UserUpdate {
  display_name?: string;
  email?: string;
  role?: string;
  is_active?: boolean;
}

export interface SsoSettings {
  oidc_enabled: boolean;
  oidc_issuer_url: string;
  oidc_client_id: string;
  oidc_client_secret: string;
  oidc_redirect_uri: string;
  oidc_group_admins: string;
  oidc_group_users: string;
}

export interface DefaultLimits {
  default_token_limit: number;
  default_message_limit: number;
  chat_message_cost: number;
  image_generation_cost: number;
}

export interface UpdateLimitsRequest {
  limits_exempt?: boolean;
  custom_monthly_token_limit?: number | null;
  unlimited?: boolean;
  monthly_token_limit?: number;
  monthly_message_limit?: number;
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