"use client";

import { useState } from "react";
import Link from "next/link";
import { ACCENT } from "../brand";

// ===================== SOCIAL PROOF =====================
export function SocialProof() {
  const stats = [
    { num: "14 521", label: "файлов выдано" },
    { num: "2 840", label: "довольных дизайнеров" },
    { num: "~8 сек", label: "средняя выдача" },
    { num: "99.2%", label: "аптайм бота" },
  ];
  const reviews = [
    "/assets/review-1.jpg",
    "/assets/review-2.jpg",
    "/assets/review-3.jpg",
    "/assets/review-4.jpg",
    "/assets/review-5.jpg",
    "/assets/review-6.jpg",
  ];
  return (
    <section style={{ padding: "100px 0", position: "relative" }}>
      <div className="container-page">
        <div
          className="card stats-strip"
          style={{ padding: "36px 32px", marginBottom: 48, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 24 }}
        >
          {stats.map((s, i) => (
            <div key={s.label} style={{ textAlign: "center", borderLeft: i ? "1px solid var(--border)" : "none" }}>
              <div style={{ fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 700, letterSpacing: "-0.04em", color: ACCENT }}>{s.num}</div>
              <div style={{ fontSize: 13, color: "var(--text-dim)", marginTop: 4 }}>{s.label}</div>
            </div>
          ))}
        </div>

        <div style={{ marginBottom: 40, display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 24 }}>
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Реальные отзывы из Telegram</div>
            <h2 className="h-section" style={{ fontSize: "clamp(32px, 4.5vw, 52px)", margin: 0, maxWidth: 700 }}>
              Скриншоты от тех, кто <span style={{ color: ACCENT }}>уже пользуется</span>.
            </h2>
          </div>
          <p style={{ maxWidth: 320, color: "var(--text-dim)", fontSize: 14, lineHeight: 1.55, margin: 0 }}>
            Без редактуры, без актёров — реальные сообщения в поддержку и боту.
          </p>
        </div>

        <div className="rev-grid" style={{ columnCount: 3, columnGap: 16 }}>
          {reviews.map((src, i) => (
            <div
              key={src}
              style={{
                breakInside: "avoid",
                marginBottom: 16,
                borderRadius: 18,
                overflow: "hidden",
                border: "1px solid var(--border)",
                background: "var(--bg-soft)",
                boxShadow: "0 12px 40px -16px rgba(0,0,0,0.4)",
              }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={src} alt={`Отзыв ${i + 1}`} loading="lazy" style={{ display: "block", width: "100%", height: "auto" }} />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ===================== FAQ =====================
type FaqItem = { section: string; n: string } | { q: string; a: React.ReactNode };

export function FAQ() {
  const items: FaqItem[] = [
    { section: "Скачивание и файлы", n: "01" },
    { q: "Файл скачивается не сразу?", a: "Если файл не скачался с первого раза — попробуй ещё раз, это решает 90% проблем." },
    { q: "Можно ли скачать файл повторно?", a: "Да, просто отправь ссылку снова. Повторные скачивания одного и того же файла не списываются с лимита в течение 24 часов." },
    { section: "Подписка и лимиты", n: "02" },
    { q: "Что считается за «скачивание»?", a: "Только успешно завершённые загрузки. Если что-то пошло не так — лимит не списывается." },
    { q: "Когда начисляются бесплатные загрузки?", a: "Бесплатные загрузки начисляются каждую среду в 3:00 ночи в размере 5 шт." },
    {
      q: "Почему цена отличается от указанной?",
      a: "Цена формируется в белорусских рублях по курсу банка, выпустившего вашу карту. Итоговая сумма может незначительно отличаться в зависимости от курса конвертации.",
    },
    { section: "Поддерживаемые платформы", n: "03" },
    {
      q: "Почему не работает ссылка?",
      a: "Убедись, что ссылка ведёт на конкретный файл, а не на категорию или поисковую выдачу. Нужна прямая ссылка на элемент. Это касается всех платформ: Freepik, Envato Elements и Motion Array.",
    },
    {
      q: "Можно добавить поддержку других платформ?",
      a: (
        <>
          Мы планируем расширение! Напиши, какие платформы тебе нужны — учтём в следующем опросе, подписывайся на{" "}
          <a href="https://t.me/FootageHub_channel" target="_blank" rel="noopener noreferrer" style={{ color: ACCENT, textDecoration: "underline" }}>
            канал
          </a>
          !
        </>
      ),
    },
  ];
  const [open, setOpen] = useState(1);
  return (
    <section id="faq" style={{ padding: "120px 0" }}>
      <div className="container-page" style={{ maxWidth: 880 }}>
        <div style={{ textAlign: "center", marginBottom: 56 }}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>Частые вопросы</div>
          <h2 className="h-section" style={{ fontSize: "clamp(36px, 5vw, 56px)", margin: 0 }}>
            Ответим до того, <br />как <span style={{ color: ACCENT }}>спросишь.</span>
          </h2>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {items.map((it, i) => {
            if ("section" in it) {
              return (
                <div key={`s-${it.n}`} style={{ display: "flex", alignItems: "center", gap: 14, padding: "32px 4px 12px" }}>
                  <span className="mono" style={{ fontSize: 12, color: ACCENT, letterSpacing: "0.08em" }}>{it.n}</span>
                  <span style={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.12em", color: "var(--text)", textTransform: "uppercase" }}>{it.section}</span>
                  <span style={{ flex: 1, height: 1, background: "var(--border)" }} />
                </div>
              );
            }
            return (
              <div key={`q-${i}`} className="card" style={{ padding: 0, overflow: "hidden" }}>
                <button
                  onClick={() => setOpen(open === i ? -1 : i)}
                  style={{ width: "100%", padding: "22px 26px", display: "flex", alignItems: "center", justifyContent: "space-between", textAlign: "left", fontSize: 17, fontWeight: 500, color: "var(--text)" }}
                >
                  <span>{it.q}</span>
                  <span
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 999,
                      display: "grid",
                      placeItems: "center",
                      background: open === i ? ACCENT : "var(--border)",
                      color: open === i ? "white" : "var(--text-dim)",
                      fontSize: 18,
                      transition: "all 0.2s",
                      transform: open === i ? "rotate(45deg)" : "rotate(0)",
                      flexShrink: 0,
                    }}
                  >
                    +
                  </span>
                </button>
                {open === i && (
                  <div style={{ padding: "0 26px 26px", fontSize: 15, lineHeight: 1.6, color: "var(--text-dim)" }}>{it.a}</div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ===================== CTA =====================
export function CTA() {
  return (
    <section style={{ padding: "80px 0", position: "relative" }}>
      <div className="container-page">
        <div
          className="card"
          style={{ padding: "60px 48px", position: "relative", overflow: "hidden", background: `linear-gradient(135deg, ${ACCENT}25, var(--bg-card))`, borderColor: ACCENT }}
        >
          <div
            className="bg-glow"
            style={{ width: 400, height: 400, top: -100, right: -100, background: `radial-gradient(circle, ${ACCENT}, transparent 70%)`, opacity: 0.4 }}
          />
          <div className="cta-grid" style={{ position: "relative", display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 32, alignItems: "center" }}>
            <div>
              <h2 className="h-section" style={{ fontSize: "clamp(32px, 4.5vw, 52px)", margin: 0, marginBottom: 16 }}>
                Хватит платить <br />стокам по $90.
              </h2>
              <p style={{ fontSize: 17, color: "var(--text-dim)", maxWidth: 520, margin: 0, marginBottom: 32 }}>
                Первые 5 файлов — бесплатно. Без карты, без подписки. Только Telegram и пара секунд.
              </p>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <Link href="/auth" className="btn btn-primary" style={{ padding: "16px 28px", fontSize: 16 }}>
                  Попробовать бесплатно →
                </Link>
                <a href="#pricing" className="btn btn-ghost" style={{ padding: "16px 28px", fontSize: 16 }}>
                  Тарифы
                </a>
              </div>
            </div>
            <div style={{ position: "relative", minHeight: 180 }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/assets/frog-coffee.png"
                alt="лягушка с кофе"
                style={{ width: "100%", maxWidth: 280, borderRadius: 18, border: "1px solid var(--border-strong)", transform: "rotate(3deg)" }}
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
