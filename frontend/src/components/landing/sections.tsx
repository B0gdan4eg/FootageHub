"use client";

import Link from "next/link";
import { ACCENT } from "../brand";

// ===================== HOW IT WORKS =====================
export function HowItWorks() {
  const steps = [
    { n: "01", title: "Вставь ссылку", desc: "Копируй URL шаблона с Envato, Freepik или Motion Array — в боте или прямо на сайте.", kbd: "Ctrl+V" },
    { n: "02", title: "Бот достаёт файл", desc: "Качаем оригинал с премиум-аккаунта за 5–10 секунд. Без водяных знаков, без обрезок.", kbd: "~ 8 сек" },
    { n: "03", title: "Скачивай и работай", desc: "Прямая ссылка прилетает в Telegram. Работает на всех устройствах.", kbd: ".zip" },
  ];
  return (
    <section id="how" style={{ padding: "120px 0", position: "relative" }}>
      <div className="container-page">
        <div style={{ textAlign: "center", marginBottom: 64 }}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>Как это работает</div>
          <h2 className="h-section" style={{ fontSize: "clamp(36px, 5vw, 60px)", margin: 0 }}>
            Три шага. Никакой <span style={{ color: ACCENT }}>магии.</span>
          </h2>
        </div>
        <div className="how-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
          {steps.map((s) => (
            <div key={s.n} className="card" style={{ padding: 28, position: "relative", overflow: "hidden" }}>
              <div style={{ display: "inline-flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
                <span
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 999,
                    border: `1px solid ${ACCENT}`,
                    color: ACCENT,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 700,
                    fontSize: 13,
                    fontFamily: "var(--font-geist-mono), monospace",
                  }}
                >
                  {s.n}
                </span>
                <span className="mono" style={{ fontSize: 11, color: "var(--text-mute)", letterSpacing: "0.12em", textTransform: "uppercase" }}>
                  step
                </span>
              </div>
              <h3 style={{ fontSize: 24, margin: 0, marginBottom: 10, letterSpacing: "-0.02em" }}>{s.title}</h3>
              <p style={{ fontSize: 15, lineHeight: 1.55, color: "var(--text-dim)", margin: 0, marginBottom: 24 }}>{s.desc}</p>
              <span className="mono" style={{ display: "inline-block", padding: "4px 10px", borderRadius: 6, background: "var(--border)", fontSize: 12, color: "var(--text-dim)" }}>
                {s.kbd}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ===================== SOURCES =====================
export function Sources() {
  const sources = [
    { name: "Envato Elements", sub: "Видео, аудио, шаблоны AE/Premiere", status: "ok", logo: "envato", files: "54M+" },
    { name: "Freepik · Magnifik", sub: "Векторы, фото, PSD, иконки", status: "ok", logo: "freepik", files: "210M+" },
    { name: "Motion Array", sub: "AE, Premiere, DaVinci, плагины", status: "maint", logo: "ma", files: "1M+" },
  ];
  return (
    <section id="sources" style={{ padding: "100px 0", position: "relative" }}>
      <div className="container-page">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 24, marginBottom: 40 }}>
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Поддерживаемые стоки</div>
            <h2 className="h-section" style={{ fontSize: "clamp(32px, 4.5vw, 52px)", margin: 0, maxWidth: 700 }}>
              Один бот — все стоки <br />в одном кармане.
            </h2>
          </div>
        </div>

        <div className="src-grid" style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 16 }}>
          {sources.map((s) => (
            <div key={s.name} className="card" style={{ padding: 24, display: "flex", alignItems: "center", gap: 20 }}>
              <div
                style={{
                  width: 64,
                  height: 64,
                  borderRadius: 14,
                  flexShrink: 0,
                  background: s.logo === "envato" ? "#00E061" : s.logo === "freepik" ? "#1273EB" : "#0a0a0a",
                  display: "grid",
                  placeItems: "center",
                  fontSize: 28,
                  fontWeight: 800,
                  color: "white",
                  fontFamily: "var(--font-geist-sans), sans-serif",
                  letterSpacing: "-0.05em",
                }}
              >
                {s.logo === "envato" && <span style={{ fontSize: 36, color: "#0a0a0a" }}>⚡</span>}
                {s.logo === "freepik" && <span style={{ fontSize: 30 }}>F</span>}
                {s.logo === "ma" && <span style={{ fontSize: 26 }}>ma</span>}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4, flexWrap: "wrap" }}>
                  <h3 style={{ margin: 0, fontSize: 19, letterSpacing: "-0.01em" }}>{s.name}</h3>
                  {s.status === "ok" && (
                    <span className="pill">
                      <span className="dot" />работает
                    </span>
                  )}
                  {s.status === "maint" && (
                    <span className="pill warn">
                      <span className="dot" />тех. работы
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 14, color: "var(--text-dim)", marginBottom: 6 }}>{s.sub}</div>
                <div className="mono" style={{ fontSize: 12, color: "var(--text-mute)" }}>{s.files} файлов в каталоге</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ===================== PRICING =====================
type Tier = {
  name: string;
  tag: string;
  rub: number;
  usd: number;
  files: number;
  perks: string[];
  cta: string;
  pop?: boolean;
};

export function Pricing({ currency, setCurrency }: { currency: "rub" | "usd"; setCurrency: (c: "rub" | "usd") => void }) {
  const tiers: Tier[] = [
    { name: "Lite", tag: "Для теста", rub: 399, usd: 4.99, files: 50, perks: ["50 файлов в месяц", "Все стоки кроме Motion Array", "Хранение 7 дней", "Поддержка в Telegram"], cta: "Начать с Lite" },
    { name: "Standard", tag: "Самый популярный", rub: 899, usd: 10.99, files: 150, perks: ["150 файлов в месяц", "Все стоки", "Хранение 30 дней", "Приоритет в очереди", "Возврат если файл не работает"], cta: "Взять Standard", pop: true },
    { name: "Pro", tag: "Для агентств", rub: 1790, usd: 21.99, files: 400, perks: ["400 файлов в месяц", "Все стоки + ранний доступ к новым", "Хранение 90 дней", "API + bulk-режим", "Личный менеджер", "Скидка на AI-генерации"], cta: "Хочу Pro" },
  ];

  return (
    <section id="pricing" style={{ padding: "120px 0", position: "relative" }}>
      <div
        className="bg-glow"
        style={{ width: 500, height: 500, top: 100, left: "50%", transform: "translateX(-50%)", background: `radial-gradient(circle, ${ACCENT}40, transparent 70%)` }}
      />
      <div className="container-page" style={{ position: "relative" }}>
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>Тарифы</div>
          <h2 className="h-section" style={{ fontSize: "clamp(36px, 5vw, 60px)", margin: 0, marginBottom: 16 }}>
            Дешевле любой <span style={{ color: ACCENT }}>подписки.</span>
          </h2>
          <p style={{ fontSize: 17, color: "var(--text-dim)", maxWidth: 520, margin: "0 auto 24px" }}>
            Не понравилось — вернём деньги в течение 24 часов, без вопросов.
          </p>
          <div style={{ display: "inline-flex", padding: 4, borderRadius: 999, background: "var(--border)", border: "1px solid var(--border)" }}>
            {(["rub", "usd"] as const).map((c) => (
              <button
                key={c}
                onClick={() => setCurrency(c)}
                style={{
                  padding: "8px 18px",
                  borderRadius: 999,
                  fontSize: 13,
                  fontWeight: 600,
                  background: currency === c ? "var(--accent)" : "transparent",
                  color: currency === c ? "white" : "var(--text-dim)",
                  transition: "all 0.2s",
                }}
              >
                {c === "rub" ? "₽ Рубли" : "$ USD"}
              </button>
            ))}
          </div>
        </div>

        <div className="price-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20, alignItems: "stretch" }}>
          {tiers.map((t) => (
            <div
              key={t.name}
              className="card"
              style={{
                padding: 32,
                position: "relative",
                borderColor: t.pop ? ACCENT : "var(--border)",
                transform: t.pop ? "scale(1.03)" : "none",
                boxShadow: t.pop ? `0 30px 80px -30px ${ACCENT}66` : "none",
                background: t.pop ? `linear-gradient(180deg, ${ACCENT}10, var(--bg-card))` : "var(--bg-card)",
                marginTop: t.pop ? 16 : 0,
                overflow: "visible",
              }}
            >
              {t.pop && (
                <div
                  style={{
                    position: "absolute",
                    top: -14,
                    left: "50%",
                    transform: "translateX(-50%)",
                    background: ACCENT,
                    color: "white",
                    fontSize: 11,
                    fontWeight: 700,
                    padding: "6px 14px",
                    borderRadius: 999,
                    letterSpacing: "0.08em",
                    whiteSpace: "nowrap",
                    zIndex: 2,
                    boxShadow: `0 8px 24px -6px ${ACCENT}`,
                  }}
                >
                  ★ ПОПУЛЯРНЫЙ
                </div>
              )}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
                <h3 style={{ margin: 0, fontSize: 24, letterSpacing: "-0.02em" }}>{t.name}</h3>
                <span className="mono" style={{ fontSize: 11, color: "var(--text-mute)" }}>{t.tag}</span>
              </div>
              <div style={{ fontSize: 13, color: "var(--text-dim)", marginBottom: 24 }}>{t.files} файлов / месяц</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginBottom: 6 }}>
                <span style={{ fontSize: 52, fontWeight: 700, letterSpacing: "-0.04em", lineHeight: 1 }}>
                  {currency === "rub" ? t.rub : t.usd}
                </span>
                <span style={{ fontSize: 22, fontWeight: 600, color: "var(--text-dim)" }}>{currency === "rub" ? "₽" : "$"}</span>
              </div>
              <div style={{ fontSize: 13, color: "var(--text-dim)", marginBottom: 28 }}>
                в месяц · {currency === "rub" ? `≈ ${(t.rub / t.files).toFixed(1)}₽` : `≈ $${(t.usd / t.files).toFixed(2)}`} за файл
              </div>
              <Link href="/payment" className={`btn ${t.pop ? "btn-primary" : "btn-ghost"}`} style={{ width: "100%", marginBottom: 24 }}>
                {t.cta}
              </Link>
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
                {t.perks.map((p) => (
                  <li key={p} style={{ display: "flex", gap: 10, fontSize: 14, color: "var(--text-dim)" }}>
                    <span style={{ color: ACCENT, flexShrink: 0 }}>✓</span>
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ===================== VS COMPARISON =====================
export function Versus() {
  const rows: [string, { text: string; neg: boolean }, { text: string; neg: boolean; big?: boolean }][] = [
    ["Доступ к Envato Elements", { text: "$33/мес", neg: true }, { text: "$11/мес", neg: false }],
    ["Доступ к Freepik Premium+", { text: "$20/мес", neg: true }, { text: "включено", neg: false }],
    ["Доступ к Motion Array", { text: "$39.99/мес", neg: true }, { text: "включено", neg: false }],
    ["Привязка к одному устройству", { text: "Да", neg: true }, { text: "Нет", neg: false }],
    ["VPN для оплаты из РФ", { text: "Нужен", neg: true }, { text: "Не нужен", neg: false }],
    ["Старт за 2 минуты", { text: "Карта + регистрация", neg: true }, { text: "Telegram + СБП", neg: false }],
    ["Итого в месяц", { text: "~$92 / 8 200₽", neg: true }, { text: "899₽", neg: false, big: true }],
  ];
  return (
    <section id="vs" style={{ padding: "100px 0" }}>
      <div className="container-page">
        <div style={{ textAlign: "center", marginBottom: 56 }}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>Сравнение</div>
          <h2 className="h-section" style={{ fontSize: "clamp(36px, 5vw, 56px)", margin: 0 }}>
            Подписки vs <span style={{ color: ACCENT }}>FootageHub</span>
          </h2>
        </div>
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div
            className="vs-row"
            style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr 1fr", padding: "20px 28px", borderBottom: "1px solid var(--border)", fontSize: 13, fontWeight: 600, color: "var(--text-dim)" }}
          >
            <div />
            <div style={{ textAlign: "center" }}>Купить отдельно</div>
            <div style={{ textAlign: "center", color: ACCENT }}>FootageHub</div>
          </div>
          {rows.map((r, i) => (
            <div
              key={r[0]}
              className="vs-row"
              style={{
                display: "grid",
                gridTemplateColumns: "1.4fr 1fr 1fr",
                padding: "18px 28px",
                borderBottom: i < rows.length - 1 ? "1px solid var(--border)" : "none",
                fontSize: 15,
                background: i === rows.length - 1 ? "color-mix(in oklab, var(--accent) 6%, transparent)" : "transparent",
              }}
            >
              <div style={{ color: "var(--text-dim)" }}>{r[0]}</div>
              <div style={{ textAlign: "center", color: "#FF6B6B", textDecoration: r[1].neg && i < rows.length - 1 ? "line-through" : "none" }}>
                {r[1].text}
              </div>
              <div style={{ textAlign: "center", color: r[2].big ? ACCENT : "var(--text)", fontWeight: r[2].big ? 700 : 600, fontSize: r[2].big ? 22 : 15 }}>
                {r[2].text}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
