import type {
  LoginRequest,
  TokenResponse,
  HealthResponse,
  User,
  Chat,
  ChatResponse,
  ChatCreate,
  ChatUpdate,
  Message,
  Usage,
  UsageEvent,
  UsageSummary,
  AuditLog,
  DashboardStats,
  SystemInfo,
  ModelInfo,
  SetupRequest,
  UserCreate,
  UserUpdate,
  Permission,
  SsoSettings,
  DefaultLimits,
  UpdateLimitsRequest,
  UserLimits,
  GeneratedImage,
  ImageGenerateRequest,
  ImageProviderSettings,
  ImageProviderSettingsUpdate,
} from "../types";

const API_URL = (import.meta as any).env?.VITE_API_URL || "";

function getToken(): string | null {
  return localStorage.getItem("nexus_token");
}

export function setToken(token: string): void {
  localStorage.setItem("nexus_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("nexus_token");
}

function extractErrorMessage(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as any).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    if (typeof detail.message === "string") return detail.message;
    if (detail.error_code === "LIMIT_REACHED") {
      const label = detail.action_type === "IMAGE_GENERATION" ? "Bildgenerierung" : "Nachricht";
      const cost = detail.cost ?? 0;
      const remaining = detail.remaining ?? 0;
      return `Limit erreicht: Für diese ${label} werden ${cost} Token benötigt, dir stehen aber nur noch ${remaining} zur Verfügung.`;
    }
  }
  if (typeof (body as any).message === "string") return (body as any).message;
  return null;
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!response.ok) {
    let message = "An error occurred";
    try {
      const body = await response.json();
      message = extractErrorMessage(body) || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export async function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const result = await request<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
  setToken(result.access_token);
  return result;
}

export async function setup(data: SetupRequest): Promise<TokenResponse> {
  const result = await request<TokenResponse>("/api/auth/setup", {
    method: "POST",
    body: JSON.stringify(data),
  });
  setToken(result.access_token);
  return result;
}

export async function getMe(): Promise<User> {
  return request<User>("/api/auth/me");
}

export async function getUsers(): Promise<User[]> {
  const data = await request<{ users: User[]; total: number }>("/api/users/");
  return data.users;
}

export async function createUser(data: UserCreate): Promise<User> {
  return request<User>("/api/users/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateUser(
  userId: string | number,
  data: UserUpdate
): Promise<User> {
  return request<User>(`/api/users/${userId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteUser(userId: string | number): Promise<void> {
  return request<void>(`/api/users/${userId}`, {
    method: "DELETE",
  });
}

export async function updateUserPermissions(
  userId: string | number,
  permissionIds: number[]
): Promise<void> {
  return request<void>(`/api/users/${userId}/permissions`, {
    method: "PUT",
    body: JSON.stringify({ permission_ids: permissionIds }),
  });
}

export async function updateUserLimits(
  userId: string | number,
  data: UpdateLimitsRequest
): Promise<void> {
  return request<void>(`/api/users/${userId}/limits`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function getUserLimitsConfig(userId: string | number): Promise<UserLimits> {
  return request<UserLimits>(`/api/admin/users/${userId}/limits`);
}

export async function getUserUsageEvents(
  userId: string | number,
  limit?: number
): Promise<UsageEvent[]> {
  const qs = limit ? `?limit=${limit}` : "";
  return request<UsageEvent[]>(`/api/users/${userId}/usage/events${qs}`);
}

export async function getUsageSummary(): Promise<UsageSummary> {
  return request<UsageSummary>("/api/admin/usage/summary");
}

export async function getUserUsage(userId: string | number): Promise<Usage[]> {
  return request<Usage[]>(`/api/users/${userId}/usage`);
}

export async function listChats(): Promise<Chat[]> {
  const data = await request<{ chats: Chat[]; total: number }>("/api/chat/");
  return data.chats;
}

export async function createChat(data?: ChatCreate): Promise<Chat> {
  return request<Chat>("/api/chat/", {
    method: "POST",
    body: JSON.stringify(data || {}),
  });
}

export async function getChat(chatId: string | number): Promise<ChatResponse> {
  return request<ChatResponse>(`/api/chat/${chatId}`);
}

export async function updateChat(
  chatId: string | number,
  data: ChatUpdate
): Promise<Chat> {
  return request<Chat>(`/api/chat/${chatId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteChat(chatId: string | number): Promise<void> {
  return request<void>(`/api/chat/${chatId}`, {
    method: "DELETE",
  });
}

export async function sendChatMessage(
  chatId: string | number,
  content: string,
  model?: string
): Promise<{ message: Message }> {
  return request<{ message: Message }>(`/api/chat/${chatId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content, model }),
  });
}

export async function* sendMessageStream(
  chatId: string | number,
  content: string,
  model?: string
): AsyncGenerator<string, void, unknown> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}/api/chat/${chatId}/messages`, {
    method: "POST",
    headers,
    body: JSON.stringify({ content, model }),
  });

  if (!response.ok) {
    let message = "Failed to send message";
    let code: string | undefined;
    try {
      const body = await response.json();
      message = extractErrorMessage(body) || message;
      if (body && typeof body === "object") {
        const detail = (body as any).detail;
        if (detail && typeof detail === "object" && typeof detail.error_code === "string") {
          code = detail.error_code;
        }
      }
    } catch {
      message = response.statusText || message;
    }
    const error = new Error(message) as Error & { code?: string };
    error.code = code;
    throw error;
  }

  if (!response.body) {
    throw new Error("No response body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";

      for (const event of events) {
        for (const line of event.split("\n")) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6).trim();
            if (!data) continue;
            try {
              const parsed = JSON.parse(data);
              if (parsed.type === "token" && parsed.content) {
                yield parsed.content;
              } else if (parsed.type === "error") {
                throw new Error(parsed.content || "Generation failed");
              }
            } catch (e) {
              if (e instanceof Error && e.message === "Generation failed") {
                throw e;
              }
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function getDashboard(): Promise<DashboardStats> {
  return request<DashboardStats>("/api/admin/dashboard");
}

export async function getLogs(params?: {
  user_id?: string;
  action?: string;
  limit?: number;
}): Promise<AuditLog[]> {
  const query = new URLSearchParams();
  if (params?.user_id) query.set("user_id", params.user_id);
  if (params?.action) query.set("action", params.action);
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  const data = await request<{ logs: AuditLog[]; total: number }>(
    `/api/admin/logs${qs ? `?${qs}` : ""}`
  );
  return data.logs;
}

export async function getSystemInfo(): Promise<SystemInfo> {
  return request<SystemInfo>("/api/admin/system");
}

export async function getModels(): Promise<ModelInfo[]> {
  const data = await request<{ models: ModelInfo[] }>("/api/admin/models");
  return data.models;
}

export async function pullModel(name: string): Promise<void> {
  return request<void>("/api/admin/models/pull", {
    method: "POST",
    body: JSON.stringify({ model: name }),
  });
}

export async function getModelStatus(): Promise<{
  ollama: string;
  default_model: string;
  default_model_present: boolean;
  model_count: number;
}> {
  return request("/api/admin/models/status");
}

export async function getPermissions(): Promise<Permission[]> {
  return request<Permission[]>("/api/permissions/");
}

export async function getSetupStatus(): Promise<{
  needs_setup: boolean;
  first_admin_configured: boolean;
}> {
  return request("/api/setup/status");
}

export async function getMyUsage(): Promise<Usage> {
  const me = await getMe();
  return {
    period: me.period,
    tokens_used: me.tokens_used_month,
    messages_used: me.messages_used_month,
    token_limit: me.unlimited
      ? -1
      : me.effective_token_limit ?? me.monthly_token_limit,
    message_limit: me.monthly_message_limit,
  };
}

export async function getSsoSettings(): Promise<SsoSettings> {
  return request<SsoSettings>("/api/admin/settings/sso");
}

export async function updateSsoSettings(
  data: Partial<SsoSettings>
): Promise<SsoSettings> {
  return request<SsoSettings>("/api/admin/settings/sso", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function getDefaultLimits(): Promise<DefaultLimits> {
  return request<DefaultLimits>("/api/admin/settings/limits");
}

export async function updateDefaultLimits(
  data: Partial<DefaultLimits>
): Promise<DefaultLimits> {
  return request<DefaultLimits>("/api/admin/settings/limits", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Image generation
// ---------------------------------------------------------------------------

const imageUrlCache = new Map<string, string>();

export async function generateImage(
  data: ImageGenerateRequest
): Promise<GeneratedImage> {
  return request<GeneratedImage>("/api/images/generate", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getImageMetadata(
  imageId: string | number
): Promise<GeneratedImage> {
  return request<GeneratedImage>(`/api/images/${imageId}`);
}

/**
 * Authenticated image loading. Plain <img> tags cannot send the bearer token,
 * so the bytes are fetched as a blob once and exposed as an object URL. The
 * URL is cached per image so repeated renders do not refetch the file.
 */
export async function getImageFileUrl(path: string): Promise<string> {
  if (imageUrlCache.has(path)) return imageUrlCache.get(path)!;
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const response = await fetch(`${API_URL}${path}`, { headers });
  if (response.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!response.ok) {
    throw new Error("Das Bild konnte nicht geladen werden.");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  imageUrlCache.set(path, url);
  return url;
}

export async function getImageProviderSettings(): Promise<ImageProviderSettings> {
  return request<ImageProviderSettings>("/api/admin/settings/images");
}

export async function updateImageProviderSettings(
  data: ImageProviderSettingsUpdate
): Promise<ImageProviderSettings> {
  return request<ImageProviderSettings>("/api/admin/settings/images", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}