import { assetProvider } from "./analytics";

const KEY = "fh_pending_asset";
const LIFETIME = 30 * 60 * 1000;

export function normalizeAssetUrl(value: string): string | null {
  try {
    const input = value.trim();
    const url = new URL(input.includes("://") ? input : `https://${input}`);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password
      || url.port || url.pathname === "/" || assetProvider(url.href) === "unknown") return null;
    return url.href;
  } catch { return null; }
}

export function saveDownloadIntent(url: string): boolean {
  const normalized = normalizeAssetUrl(url);
  if (!normalized) return false;
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ url: normalized, expires: Date.now() + LIFETIME }));
    return true;
  } catch { return false; }
}

export function takeDownloadIntent(): string {
  try {
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    const value = JSON.parse(raw || "null");
    return typeof value?.url === "string" && typeof value.expires === "number"
      && value.expires > Date.now() && value.expires <= Date.now() + LIFETIME
      ? normalizeAssetUrl(value.url) ?? "" : "";
  } catch { return ""; }
}

export function assetFileName(value: string): string {
  try {
    const url = new URL(value);
    const segment = url.pathname.replace(/\/$/, "").split("/").pop();
    if (!segment) return url.hostname;
    try { return decodeURIComponent(segment); } catch { return segment; }
  } catch { return "File"; }
}
