"use client";

import { CSSProperties } from "react";
import Link from "next/link";
import { PageShell } from "@/components/page-shell";
import { useHomeHref } from "@/lib/language";
import { ExternalLink } from "lucide-react";

const FEATURES = [
  { ico: "🎬", title: "Motion-шаблоны", sub: "Генерация .aep / .mogrt из текстового брифа. Импортируешь в After Effects и работаешь дальше." },
  { ico: "🎨", title: "Векторы и постеры", sub: "AI рисует векторные иллюстрации в нужном стиле. Сразу .ai / .svg, без растровых артефактов." },
  { ico: "🔁", title: "Бесконечные правки", sub: "«Сделай ярче», «убери логотип», «другой ритм». Чат с AI прямо в Telegram, итераций сколько надо." },
];

export default function AIPage() {
  const homeHref = useHomeHref();

  // Локальный акцент страницы — розовый (как в дизайне ai.html)
  const pink: CSSProperties = { ["--accent" as string]: "#FF2EA1" } as CSSProperties;

  return (
    <PageShell>
      <main style={{ ...pink, position: "relative", overflow: "hidden", minHeight: "calc(100vh - 68px)" }}>
        <div className="bg-grid" />
        <div className="bg-glow" style={{ width: 700, height: 700, top: -100, right: -200, background: "radial-gradient(circle, var(--accent), transparent 70%)", opacity: 0.5 }} />
        <div className="bg-glow" style={{ width: 500, height: 500, bottom: -100, left: -100, background: "radial-gradient(circle, #2D6BFF, transparent 70%)", opacity: 0.3 }} />

        <div className="container-page" style={{ position: "relative", padding: "60px 24px" }}>
          <div className="ai-grid" style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: 60, alignItems: "center" }}>
            <div>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "6px 14px",
                  borderRadius: 999,
                  background: "rgba(255, 46, 161, 0.15)",
                  color: "var(--accent)",
                  fontSize: 12,
                  fontWeight: 600,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  marginBottom: 24,
                }}
              >
                <span style={{ width: 8, height: 8, borderRadius: 999, background: "var(--accent)", animation: "pulse 1.5s infinite" }} />
                Скоро · в разработке
              </div>
              <h1 className="h-display" style={{ fontSize: "clamp(48px, 7vw, 88px)", margin: 0, marginBottom: 24, letterSpacing: "-0.04em" }}>
                AI, который <br />
                <span
                  style={{
                    background: "linear-gradient(90deg, var(--accent), #2D6BFF)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                    backgroundClip: "text",
                    color: "transparent",
                  }}
                >
                  генерит шаблоны.
                </span>
              </h1>
              <p style={{ fontSize: 19, lineHeight: 1.55, color: "var(--text-dim)", maxWidth: 540, margin: 0, marginBottom: 36 }}>
                Опишешь идею текстом — получишь готовый <span className="mono" style={{ color: "var(--text)" }}>.aep</span>,{" "}
                <span className="mono" style={{ color: "var(--text)" }}>.psd</span> или вектор. Бесплатные правки. Прямо в Telegram.
              </p>

              <a href="https://t.me/FootageHub_channel" target="_blank" rel="noopener noreferrer"
                className="btn btn-primary" style={{ marginBottom: 16, whiteSpace: "normal", textAlign: "center" }}>
                <ExternalLink size={18} aria-hidden="true" style={{ flexShrink: 0 }} />
                Новости о запуске в Telegram
              </a>
              <div style={{ fontSize: 12, color: "var(--text-mute)" }}>
                Анонс появится в канале новостей.
              </div>
            </div>

            {/* Right: mock generation card */}
            <div style={{ position: "relative" }}>
              <div className="card" style={{ padding: 24, position: "relative", zIndex: 2, boxShadow: "0 30px 80px -20px rgba(0,0,0,0.5)" }}>
                <div className="flex items-center justify-between" style={{ marginBottom: 18 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em" }}>AI Generator</span>
                  <span className="pill" style={{ fontSize: 11, color: "var(--accent)", borderColor: "rgba(255,46,161,0.3)" }}>
                    <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--accent)" }} />preview
                  </span>
                </div>

                <div style={{ padding: 14, background: "var(--bg-soft)", borderRadius: 10, fontFamily: "var(--font-geist-mono), monospace", fontSize: 13, marginBottom: 14, color: "var(--text-dim)" }}>
                  → &quot;Минималистичная заставка для тревел-блога,
                  <br />
                  &nbsp;&nbsp;&nbsp;6 секунд, в стиле Wes Anderson&quot;
                </div>

                <div
                  style={{
                    aspectRatio: "16/9",
                    borderRadius: 10,
                    marginBottom: 14,
                    background: "linear-gradient(135deg, #2D6BFF, #FF2EA1, #FFA82E)",
                    position: "relative",
                    overflow: "hidden",
                    display: "grid",
                    placeItems: "center",
                  }}
                >
                  <div style={{ fontSize: 11, color: "rgba(255,255,255,0.8)", fontFamily: "var(--font-geist-mono), monospace", letterSpacing: "0.1em", background: "rgba(0,0,0,0.4)", padding: "6px 12px", borderRadius: 999 }}>
                    генерация · 47%
                  </div>
                  <div style={{ position: "absolute", inset: 0, background: "repeating-linear-gradient(45deg, transparent 0 20px, rgba(255,255,255,0.04) 20px 40px)" }} />
                </div>

                <div className="flex items-center justify-between" style={{ fontSize: 12, color: "var(--text-dim)" }}>
                  <span className="mono">trip-intro-v2.aep</span>
                  <span>~ 12 сек</span>
                </div>
              </div>
              <div
                style={{
                  position: "absolute",
                  top: -20,
                  right: -20,
                  zIndex: 1,
                  padding: "8px 16px",
                  borderRadius: 999,
                  background: "var(--bg-soft)",
                  border: "1px solid var(--border-strong)",
                  fontSize: 12,
                  fontWeight: 600,
                  transform: "rotate(8deg)",
                }}
              >
                ✦ работает на свежей лягушке
              </div>
            </div>
          </div>

          {/* Features */}
          <div style={{ marginTop: 100 }}>
            <h2 className="h-section" style={{ fontSize: "clamp(28px, 4vw, 44px)", margin: 0, marginBottom: 32, textAlign: "center" }}>
              Что будет уметь
            </h2>
            <div className="feat-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
              {FEATURES.map((f) => (
                <div key={f.title} className="card" style={{ padding: 28, opacity: 0.85 }}>
                  <div style={{ fontSize: 32, marginBottom: 14 }}>{f.ico}</div>
                  <h3 style={{ margin: 0, fontSize: 18, marginBottom: 8, letterSpacing: "-0.01em" }}>{f.title}</h3>
                  <p style={{ margin: 0, fontSize: 14, color: "var(--text-dim)", lineHeight: 1.5 }}>{f.sub}</p>
                </div>
              ))}
            </div>
          </div>

          <div style={{ textAlign: "center", marginTop: 60, paddingTop: 40, borderTop: "1px solid var(--border)" }}>
            <Link href={homeHref} style={{ fontSize: 14, color: "var(--text-dim)" }}>
              ← Вернуться на главную
            </Link>
          </div>
        </div>
      </main>
    </PageShell>
  );
}
