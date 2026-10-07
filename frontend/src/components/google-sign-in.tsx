"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import { clearToken } from "@/lib/auth";
import { trackEvent } from "@/lib/analytics";

export function GoogleSignIn({ connect = false, returnPath = "/dashboard" }: { connect?: boolean; returnPath?: string }) {
  const [enabled, setEnabled] = useState(false);
  const [connected, setConnected] = useState(false);
  const [email, setEmail] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const completed = () => {
      if (connect && document.cookie.split("; ").includes("google_login_done=1") && trackEvent("login", { method: "google" })) {
        trackEvent("registration_completed", { method: "google" });
        document.cookie = "google_login_done=; Max-Age=0; path=/; Secure; SameSite=Lax";
      }
    };
    completed();
    window.addEventListener("fh-analytics-ready", completed);
    void api.get<{ enabled: boolean }>("/auth/google/config").then(({ data }) => {
      if (active) setEnabled(data.enabled);
    }).catch(() => {});
    if (connect) void api.get<{ connected: boolean; email: string | null }>("/auth/google/identity").then(({ data }) => {
      if (active) { setConnected(data.connected); setEmail(data.email); }
    }).catch(() => {});
    const reason = new URLSearchParams(window.location.search).get("google_error");
    if (reason) setError(reason === "conflict" ? "Этот Google-аккаунт уже связан с другим аккаунтом. Войдите через Telegram и подключите Google в личном кабинете." : reason === "cancelled" ? "Вход через Google отменён." : "Не удалось завершить вход через Google. Попробуйте снова.");
    return () => { active = false; window.removeEventListener("fh-analytics-ready", completed); };
  }, [connect]);
  const start = async () => {
    setBusy(true); setError("");
    try {
      const { data } = await api.post<{ url: string }>("/auth/google/start", { connect, return_path: returnPath });
      if (!connect) trackEvent("registration_started", { method: "google" });
      window.location.assign(data.url);
    } catch { setBusy(false); setError("Не удалось открыть Google. Попробуйте снова."); }
  };
  if (!enabled && !error) return null;
  return <div style={{ margin: "20px 0", textAlign: "center" }}>
    {connected ? <p>Google подключён: {email}</p> : enabled && <>
      <button type="button" onClick={() => void start()} disabled={busy} style={{ width: "100%", padding: "14px 20px", borderRadius: 12, background: "white", color: "#202124", border: "1px solid #dadce0", fontSize: 16, cursor: "pointer" }}>
        {busy ? "Открываем Google…" : connect ? "Подключить Google" : "Продолжить с Google"}
      </button>
      <p style={{ fontSize: 13, color: "var(--text-dim)", marginTop: 10 }}>{connect ? "Google будет подключён к текущему аккаунту. Баланс и история сохранятся." : "Уже пользуетесь Telegram? Войдите через Telegram и подключите Google в личном кабинете."}</p>
    </>}
    {error && <p role="alert" style={{ color: "var(--red, #ef4444)" }}>{error}</p>}
    {connect && <button type="button" onClick={() => {
      void api.post("/auth/logout").then(() => { clearToken(); window.location.assign("/auth"); }).catch(() => setError("Не удалось выйти. Попробуйте снова."));
    }} style={{ marginTop: 10 }}>Выйти из аккаунта</button>}
  </div>;
}
