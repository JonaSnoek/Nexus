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
  AuditLog,
  DashboardStats,
  SystemInfo,
  ModelInfo,
  SetupRequest,
  UserCreate,
  UserUpdate,
  Permission,
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
      message = body.detail || body.message || message;
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
  data: { daily_token_limit: number; daily_message_limit: number }
): Promise<void> {
  return request<void>(`/api/users/${userId}/limits`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
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
    try {
      const body = await response.json();
      message = body.detail || body.message || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
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
  const usage = await getUserUsage(String(me.id));
  const today = new Date().toISOString().slice(0, 10);
  const todayUsage = usage.find((u) => u.date === today);
  return {
    date: today,
    tokens_used: todayUsage?.tokens_used || 0,
    messages_used: todayUsage?.messages_used || 0,
    token_limit: me.daily_token_limit,
    message_limit: me.daily_message_limit,
  };
}