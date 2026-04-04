/**
 * Typed API client for FootageHub Web API.
 * Uses axios with automatic JWT auth header injection.
 */

import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "https://envato-freepik-download.store/api",
  withCredentials: true,
});

// Добавляем JWT из cookie в каждый запрос
api.interceptors.request.use((config) => {
  if (typeof document !== "undefined") {
    const token = getCookie("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Редирект на /auth при 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      window.location.href = "/auth";
    }
    return Promise.reject(error);
  }
);

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return match ? decodeURIComponent(match[2]) : null;
}

export default api;

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const authApi = {
  sendCode: (phone: string) => api.post("/auth/send-code", { phone }),

  verifyCode: (phone: string, code: string) =>
    api.post<{ access_token: string; user: User }>("/auth/verify-code", { phone, code }),

  me: () => api.get<User>("/auth/me"),

  linkBot: (referral_code: string) =>
    api.post<{ request_id: number; expires_at: string }>("/auth/link-bot", { referral_code }),

  linkStatus: (request_id: number) =>
    api.get<{ status: string; access_token?: string }>(`/auth/link-status/${request_id}`),

  telegramConfig: () => api.get<{ bot_username: string }>("/auth/telegram/config"),

  telegramLogin: (data: TelegramAuthResult) =>
    api.post<{ access_token: string; user: User }>("/auth/telegram", data),
};

export interface TelegramAuthResult {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
}

// ─── Users ────────────────────────────────────────────────────────────────────

export const usersApi = {
  profile: () => api.get<User>("/users/me"),
  downloads: (page = 1) => api.get(`/users/me/downloads?page=${page}`),
  subscriptions: () => api.get("/users/me/subscriptions"),
  aiGenerations: (page = 1) => api.get(`/users/me/ai-generations?page=${page}`),
};

// ─── Downloads ────────────────────────────────────────────────────────────────

export const downloadsApi = {
  download: (url: string, provider?: string) =>
    api.post<{ download_url: string; remaining_credits: number; is_file_token: boolean }>(
      "/downloads/",
      { url, provider }
    ),
};

// ─── AI ───────────────────────────────────────────────────────────────────────

export const aiApi = {
  pricing: () => api.get("/ai/pricing"),

  generate: (data: {
    type: "IMAGE" | "VIDEO" | "IMAGE_TO_VIDEO";
    provider: string;
    prompt: string;
    parameters?: Record<string, unknown>;
  }) => api.post<{ task_id: number; status: string; credits_spent: number }>("/ai/generate", data),

  status: (task_id: number) =>
    api.get<{ task_id: number; status: string; result_url?: string; error_message?: string }>(
      `/ai/status/${task_id}`
    ),

  history: () => api.get("/ai/history"),
};

// ─── Payments ─────────────────────────────────────────────────────────────────

export const paymentsApi = {
  plans: () => api.get("/payments/plans"),
  create: (plan_key: string, provider: "webpay" | "cryptobot") =>
    api.post<{ invoice_url: string; order_id: string }>("/payments/create", {
      plan_key,
      provider,
    }),
  history: () => api.get("/payments/history"),
};

// ─── Admin ────────────────────────────────────────────────────────────────────

export const adminApi = {
  users: (page = 1, search?: string) =>
    api.get(`/admin/users?page=${page}${search ? `&search=${search}` : ""}`),
  user: (id: number) => api.get(`/admin/users/${id}`),
  updateUser: (id: number, data: { role?: string; credits?: number; ai_credits?: number }) =>
    api.patch(`/admin/users/${id}`, data),
  stats: () => api.get("/admin/stats"),
};

// ─── Types ────────────────────────────────────────────────────────────────────

export interface User {
  id: number;
  phone_number: string | null;
  username: string | null;
  credits: number;
  ai_credits: number;
  ai_credits_used?: number;
  role: string;
  referral_code: string | null;
}
