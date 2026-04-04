/**
 * Auth helpers: save/clear JWT token in cookies.
 */

export function setToken(token: string): void {
  // httpOnly cookie нельзя установить напрямую из JS
  // Устанавливаем через обычный cookie (фронтенд)
  const expires = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toUTCString();
  document.cookie = `access_token=${encodeURIComponent(token)}; expires=${expires}; path=/; SameSite=Lax`;
}

export function clearToken(): void {
  document.cookie = "access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
}

export function getToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(^| )access_token=([^;]+)/);
  return match ? decodeURIComponent(match[2]) : null;
}

export function isAuthenticated(): boolean {
  return !!getToken();
}
