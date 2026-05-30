"use client";

import { useState } from "react";
import Link from "next/link";
import { ACCENT } from "../brand";

export function Hero() {
  const [url, setUrl] = useState("");
  const [stage, setStage] = useState<"idle" | "loading" | "ready">("idle");
  const fakeFile = "After-Effects-Cinematic-Trailer.aep";

  const submit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!url) return;
    setStage("loading");
    setTimeout(() => setStage("ready"), 1200);
  };

  return (
    <section style={{ position: "relative", overflow: "hidden", paddingTop: 40, paddingBottom: 80 }}>
      <div className="bg-grid" />
      <div
        className="bg-glow"
        style={{
          width: 600,
          height: 600,
          top: -200,
          left: "50%",
          transform: "translateX(-50%)",
          background: `radial-gradient(circle, ${ACCENT}, transparent 70%)`,
        }}
      />
      <div
        className="bg-glow"
        style={{
          width: 500,
          height: 500,
          top: 80,
          right: -100,
          background: "radial-gradient(circle, var(--pink), transparent 70%)",
          opacity: 0.25,
        }}
      />

      <div className="container-page" style={{ position: "relative" }}>
        <div
          className="hero-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "1.2fr 1fr",
            gap: 48,
            alignItems: "center",
            paddingTop: 60,
            paddingBottom: 40,
          }}
        >
          {/* Left: copy */}
          <div>
            <div className="flex items-center gap-2" style={{ display: "inline-flex", marginBottom: 28 }}>
              <span className="pill">
                <span className="dot" />
                Бот в строю · 14 521 файлов выдано
              </span>
            </div>
            <h1
              className="h-display hero-headline"
              style={{ fontSize: "clamp(48px, 6.5vw, 88px)", margin: 0, marginBottom: 24 }}
            >
              Устал искать,
              <br />
              <span style={{ position: "relative", display: "inline-block" }}>
                <span style={{ color: ACCENT }}>где взять шаблоны?</span>
                <svg
                  viewBox="0 0 300 20"
                  style={{ position: "absolute", left: 0, right: 0, bottom: -8, width: "100%", height: 14 }}
                >
                  <path
                    d="M 4 12 Q 80 2, 150 10 T 296 8"
                    stroke={ACCENT}
                    strokeWidth="3"
                    fill="none"
                    strokeLinecap="round"
                    opacity="0.6"
                  />
                </svg>
              </span>
            </h1>
            <p style={{ fontSize: 19, lineHeight: 1.5, color: "var(--text-dim)", maxWidth: 540, margin: 0, marginBottom: 36 }}>
              Вставь ссылку с Envato, Freepik или Motion Array — забери файл за 5–10 секунд. Без подписок, без танцев.
            </p>

            {/* URL paster (демо) */}
            <form
              onSubmit={submit}
              className="card"
              style={{
                padding: 8,
                display: "flex",
                gap: 8,
                alignItems: "center",
                maxWidth: 560,
                marginBottom: 20,
                borderColor: stage === "ready" ? "var(--green)" : "var(--border-strong)",
                transition: "border-color 0.3s",
              }}
            >
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 8,
                  background: "var(--border)",
                  display: "grid",
                  placeItems: "center",
                  color: "var(--text-dim)",
                  flexShrink: 0,
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                </svg>
              </div>
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="elements.envato.com/..."
                style={{
                  flex: 1,
                  background: "transparent",
                  border: "none",
                  outline: "none",
                  color: "var(--text)",
                  fontSize: 15,
                  fontFamily: "var(--font-geist-mono), monospace",
                  padding: "8px 4px",
                }}
              />
              <button type="submit" className="btn btn-primary" style={{ padding: "12px 20px", fontSize: 14 }}>
                {stage === "idle" && "→ Получить"}
                {stage === "loading" && (
                  <span className="flex items-center gap-2">
                    <span className="spinner" />
                    Ищу…
                  </span>
                )}
                {stage === "ready" && "✓ Готово"}
              </button>
            </form>

            {stage === "ready" && (
              <div
                className="card"
                style={{
                  padding: 16,
                  maxWidth: 560,
                  marginBottom: 20,
                  borderColor: "var(--green)",
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                }}
              >
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 8,
                    background: "rgba(0, 224, 97, 0.15)",
                    color: "var(--green)",
                    display: "grid",
                    placeItems: "center",
                  }}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{fakeFile}</div>
                  <div style={{ fontSize: 12, color: "var(--text-dim)" }} className="mono">
                    218 МБ · готово к скачиванию
                  </div>
                </div>
                <Link href="/auth" className="btn btn-primary" style={{ padding: "8px 14px", fontSize: 13 }}>
                  Скачать
                </Link>
              </div>
            )}

            <div className="flex items-center gap-4" style={{ flexWrap: "wrap", fontSize: 13, color: "var(--text-dim)" }}>
              <span className="flex items-center gap-2">
                <span style={{ color: "var(--green)" }}>✓</span> Без VPN
              </span>
              <span className="flex items-center gap-2">
                <span style={{ color: "var(--green)" }}>✓</span> Авторизация в 2 клика
              </span>
            </div>
          </div>

          {/* Right: tired frog */}
          <div className="hero-frog" style={{ position: "relative", minHeight: 480 }}>
            <FrogScene />
          </div>
        </div>
      </div>
    </section>
  );
}

function FrogScene() {
  return (
    <div style={{ position: "relative", width: "100%", height: "100%", minHeight: 480, display: "grid", placeItems: "center" }}>
      <div
        style={{
          position: "absolute",
          width: 380,
          height: 380,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${ACCENT}55, transparent 65%)`,
          filter: "blur(40px)",
        }}
      />
      {/* speech bubble */}
      <div
        style={{
          position: "absolute",
          top: 30,
          left: 20,
          zIndex: 3,
          background: "var(--bg-soft)",
          border: "1px solid var(--border-strong)",
          padding: "12px 16px",
          borderRadius: 18,
          fontSize: 14,
          fontWeight: 500,
          maxWidth: 220,
          boxShadow: "0 12px 40px -12px rgba(0,0,0,0.5)",
          transform: "rotate(-3deg)",
        }}
      >
        «опять Envato $33/мес?»
        <div
          style={{
            position: "absolute",
            bottom: -8,
            left: 30,
            width: 0,
            height: 0,
            borderLeft: "8px solid transparent",
            borderRight: "8px solid transparent",
            borderTop: "8px solid var(--bg-soft)",
          }}
        />
      </div>

      {/* price tags */}
      <div
        className="float-tag"
        style={{
          position: "absolute",
          top: 80,
          right: 10,
          zIndex: 3,
          background: "#0a0a0a",
          border: "1px solid #2a2a2a",
          padding: "8px 14px",
          borderRadius: 14,
          display: "flex",
          gap: 8,
          alignItems: "center",
          transform: "rotate(6deg)",
        }}
      >
        <div style={{ width: 18, height: 18, borderRadius: 4, background: "#00E061" }} />
        <span style={{ fontSize: 12, fontWeight: 600, color: "white" }}>$33/мес</span>
        <span style={{ fontSize: 11, color: "#888", textDecoration: "line-through" }}>Envato</span>
      </div>
      <div
        className="float-tag float-tag-2"
        style={{
          position: "absolute",
          top: 130,
          right: 80,
          zIndex: 3,
          background: "#0a0a0a",
          border: "1px solid #2a2a2a",
          padding: "8px 14px",
          borderRadius: 14,
          display: "flex",
          gap: 8,
          alignItems: "center",
          transform: "rotate(-4deg)",
        }}
      >
        <div style={{ width: 18, height: 18, borderRadius: 4, background: "#1273EB" }} />
        <span style={{ fontSize: 12, fontWeight: 600, color: "white" }}>$20/мес</span>
        <span style={{ fontSize: 11, color: "#888", textDecoration: "line-through" }}>Freepik</span>
      </div>

      {/* the frog */}
      <div
        style={{
          position: "relative",
          zIndex: 2,
          width: "100%",
          maxWidth: 420,
          aspectRatio: "3/4",
          borderRadius: 24,
          overflow: "hidden",
          border: "1px solid var(--border-strong)",
          background: "#1a1a1a",
          boxShadow: "0 30px 80px -20px rgba(0,0,0,0.6)",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/assets/frog-tired.jpg"
          alt="уставшая лягушка"
          style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
        />
        <div
          style={{
            position: "absolute",
            bottom: 16,
            left: 16,
            right: 16,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "10px 14px",
            borderRadius: 12,
            background: "rgba(10, 10, 14, 0.85)",
            backdropFilter: "blur(12px)",
            border: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          <span style={{ fontSize: 12, fontWeight: 600, color: "white" }}>FROG.exe</span>
          <span style={{ fontSize: 11, color: "#9298A8", fontFamily: "var(--font-geist-mono), monospace" }}>
            not_responding
          </span>
        </div>
      </div>
    </div>
  );
}

export function StockMarquee() {
  const items = ["ENVATO ELEMENTS", "✦", "FREEPIK", "✦", "MOTION ARRAY", "✦", "STORYBLOCKS", "✦", "EPIDEMIC SOUND", "✦", "ARTLIST", "✦"];
  const all = [...items, ...items, ...items];
  return (
    <div
      style={{
        borderTop: "1px solid var(--border)",
        borderBottom: "1px solid var(--border)",
        padding: "20px 0",
        overflow: "hidden",
        maskImage: "linear-gradient(90deg, transparent, black 10%, black 90%, transparent)",
        WebkitMaskImage: "linear-gradient(90deg, transparent, black 10%, black 90%, transparent)",
      }}
    >
      <div style={{ display: "flex", gap: 48, whiteSpace: "nowrap", animation: "marquee 35s linear infinite", width: "max-content" }}>
        {all.map((it, i) => (
          <span
            key={i}
            className="mono"
            style={{ fontSize: 18, fontWeight: 600, letterSpacing: "0.1em", color: it === "✦" ? "var(--accent)" : "var(--text-dim)" }}
          >
            {it}
          </span>
        ))}
      </div>
    </div>
  );
}
