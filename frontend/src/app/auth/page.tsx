"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { qrApi } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { PageShell } from "@/components/page-shell";

type Status = "init" | "waiting" | "confirmed" | "expired" | "error";

const TG_BLUE = "#2BAEEC";

function TgIcon({ size = 32, color = "white" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 240 240" fill={color} aria-hidden="true">
      <path d="M120 0c66.27 0 120 53.73 120 120s-53.73 120-120 120S0 186.27 0 120 53.73 0 120 0zm55.85 79.96c-1.6-.78-7.46.06-7.46.06l-99.18 39.86s-5.6 1.96-5 5.86c.6 3.9 5.7 5.66 5.7 5.66l25.32 8.16 9.86 31.2s1.18 4 5.16 4.06c2.96.04 4.86-2.46 4.86-2.46l16.36-15.96 23.86 17.42s7.06 4.6 11.86-1.86c4.8-6.46 18.06-89.66 18.06-89.66s.46-3.6-1.4-4.4z" />
    </svg>
  );
}

function AuthPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get("redirect") || "/dashboard";

  const [status, setStatus] = useState<Status>("init");
  const [token, setTok] = useState<string | null>(null);
  const [deeplink, setDeeplink] = useState<string>("");
  const [expiresAt, setExpiresAt] = useState<number>(0);
  const [secondsLeft, setSecondsLeft] = useState<number>(0);
  const [error, setError] = useState<string>("");

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearTimers = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (tickRef.current) clearInterval(tickRef.current);
    pollRef.current = null;
    tickRef.current = null;
  }, []);

  const startSession = useCallback(async () => {
    clearTimers();
    setError("");
    setStatus("init");
    try {
      const res = await qrApi.start();
      setTok(res.data.token);
      setDeeplink(res.data.deeplink);
      setExpiresAt(new Date(res.data.expires_at).getTime());
      setStatus("waiting");
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || "Не удалось создать сессию входа");
      setStatus("error");
    }
  }, [clearTimers]);

  // Создаём QR-сессию при монтировании
  useEffect(() => {
    startSession();
    return clearTimers;
  }, [startSession, clearTimers]);

  // Поллинг статуса + обратный отсчёт, пока ждём подтверждения
  useEffect(() => {
    if (status !== "waiting" || !token) return;

    const tick = () => {
      const left = Math.max(0, Math.round((expiresAt - Date.now()) / 1000));
      setSecondsLeft(left);
      if (left <= 0) {
        clearTimers();
        setStatus("expired");
      }
    };
    tick();
    tickRef.current = setInterval(tick, 1000);

    pollRef.current = setInterval(async () => {
      try {
        const res = await qrApi.status(token);
        if (res.data.status === "CONFIRMED" && res.data.access_token) {
          clearTimers();
          setToken(res.data.access_token);
          setStatus("confirmed");
          setTimeout(() => router.push(redirect), 900);
        } else if (res.data.status === "EXPIRED" || res.data.status === "REJECTED") {
          clearTimers();
          setStatus("expired");
        }
      } catch {
        /* временная сетевая ошибка — продолжаем поллинг */
      }
    }, 2000);

    return clearTimers;
  }, [status, token, expiresAt, redirect, router, clearTimers]);

  const mm = Math.floor(secondsLeft / 60);
  const ss = String(secondsLeft % 60).padStart(2, "0");

  return (
    <PageShell>
      <div
        style={{
          position: "relative",
          minHeight: "calc(100vh - 68px)",
          display: "grid",
          placeItems: "center",
          padding: "40px 24px",
          overflow: "hidden",
        }}
      >
        <div className="bg-grid" />
        <div
          className="bg-glow"
          style={{
            width: 600,
            height: 600,
            top: "20%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            background: "radial-gradient(circle, var(--accent), transparent 70%)",
          }}
        />

        <div
          className="card"
          style={{ width: "100%", maxWidth: 460, padding: 40, position: "relative", zIndex: 2 }}
        >
          {/* Header */}
          <div style={{ textAlign: "center", marginBottom: 28 }}>
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: 16,
                background: "linear-gradient(135deg, #229ED9, #2BAEEC)",
                display: "inline-grid",
                placeItems: "center",
                marginBottom: 20,
                boxShadow: "0 12px 40px -8px rgba(34, 158, 217, 0.5)",
              }}
            >
              <TgIcon size={32} />
            </div>
            <h1
              className="h-display"
              style={{ fontSize: 34, margin: 0, marginBottom: 10, letterSpacing: "-0.03em" }}
            >
              Войти через <span style={{ color: TG_BLUE }}>Telegram</span>
            </h1>
            <p style={{ fontSize: 15, color: "var(--text-dim)", margin: 0, lineHeight: 1.5 }}>
              Никаких паролей и регистраций. Отсканируй QR или открой бота — и ты внутри.
            </p>
          </div>

          {/* Init */}
          {status === "init" && (
            <div style={{ textAlign: "center", padding: "30px 0" }}>
              <div
                style={{
                  width: 64,
                  height: 64,
                  margin: "0 auto 18px",
                  borderRadius: "50%",
                  border: "3px solid var(--border)",
                  borderTopColor: TG_BLUE,
                  animation: "spin 1s linear infinite",
                }}
              />
              <div style={{ fontSize: 15, color: "var(--text-dim)" }}>Готовим QR-код…</div>
            </div>
          )}

          {/* Waiting — QR + deep-link + countdown */}
          {status === "waiting" && (
            <div>
              <div
                style={{
                  background: "white",
                  borderRadius: 16,
                  padding: 16,
                  width: 240,
                  height: 240,
                  margin: "0 auto 20px",
                  display: "grid",
                  placeItems: "center",
                }}
              >
                <QRCodeSVG value={deeplink} size={208} level="M" bgColor="#ffffff" fgColor="#000000" />
              </div>

              <a
                href={deeplink}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-tg"
                style={{ width: "100%", padding: "14px 24px", fontSize: 15, marginBottom: 16 }}
              >
                <TgIcon size={18} color="currentColor" />
                Открыть в Telegram
              </a>

              <div
                style={{
                  padding: 14,
                  borderRadius: 12,
                  background: "var(--bg-soft)",
                  border: "1px dashed var(--border-strong)",
                  textAlign: "center",
                }}
              >
                <div style={{ fontSize: 14, fontWeight: 500 }}>
                  ⏳ Ждём подтверждения в Telegram:{" "}
                  <span className="mono" style={{ color: "var(--text)" }}>
                    {mm}:{ss}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 6 }}>
                  Отсканируй камерой телефона или нажми кнопку выше, затем нажми «Подтвердить вход» в боте.
                </div>
              </div>
            </div>
          )}

          {/* Confirmed */}
          {status === "confirmed" && (
            <div style={{ textAlign: "center", padding: "20px 0" }}>
              <div
                style={{
                  width: 72,
                  height: 72,
                  margin: "0 auto 20px",
                  borderRadius: "50%",
                  background: "rgba(0, 224, 97, 0.15)",
                  color: "var(--green)",
                  display: "grid",
                  placeItems: "center",
                  fontSize: 36,
                }}
              >
                ✓
              </div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>Вход подтверждён!</div>
              <div style={{ fontSize: 13, color: "var(--text-dim)", marginTop: 6 }}>
                Открываем личный кабинет…
              </div>
            </div>
          )}

          {/* Expired / error */}
          {(status === "expired" || status === "error") && (
            <div style={{ textAlign: "center", padding: "10px 0" }}>
              <div style={{ fontSize: 15, marginBottom: 16, color: "var(--text-dim)" }}>
                {status === "expired"
                  ? "⌛ Срок действия QR истёк."
                  : error || "Что-то пошло не так."}
              </div>
              <button
                onClick={startSession}
                className="btn btn-primary"
                style={{ width: "100%", padding: "14px 24px", fontSize: 15 }}
              >
                Обновить QR
              </button>
            </div>
          )}

          <div
            style={{ textAlign: "center", fontSize: 12, color: "var(--text-mute)", marginTop: 20 }}
          >
            Авторизуясь, ты соглашаешься с{" "}
            <a
              href="/assets/public_offer_footagehub.pdf"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: "var(--text-dim)", textDecoration: "underline" }}
            >
              офертой
            </a>{" "}
            и политикой
          </div>
        </div>
      </div>
    </PageShell>
  );
}

export default function AuthPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: "100vh", background: "var(--bg)" }} />}>
      <AuthPageInner />
    </Suspense>
  );
}
