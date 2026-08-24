"use client";

import Link from "next/link";
import { Logo } from "./brand";
import { LocalizedContent, type LandingLanguage } from "./landing/localized-content";

type Contact = { label: string; href: string; logo: string; shadow: string };

const PRODUCT: [string, string][] = [
  ["Главная", "/"],
  ["Тарифы", "/#pricing"],
  ["Как работает", "/#how"],
  ["AI-генерации", "/ai"],
];

const ACCOUNT: [string, string][] = [
  ["Войти", "/auth"],
  ["Личный кабинет", "/dashboard"],
  ["Оплата", "/payment"],
];

const CONTACTS: Contact[] = [
  {
    label: "Telegram-бот",
    href: "https://t.me/FootageHub_bot",
    logo: "/assets/brand-logo-green.png",
    shadow: "#22d36b",
  },
  {
    label: "Канал новостей",
    href: "https://t.me/FootageHub_channel",
    logo: "/assets/frog-views.jpg",
    shadow: "#2D6BFF",
  },
  {
    label: "Поддержка",
    href: "https://t.me/FootageHub_support",
    logo: "/assets/brand-logo-pink.png",
    shadow: "#FF2EA1",
  },
];

export function SiteFooter({ language = "ru" }: { language?: LandingLanguage }) {
  return (
    <LocalizedContent language={language}>
    <footer style={{ borderTop: "1px solid var(--border)", padding: "60px 0 40px", marginTop: 40 }}>
      <div className="container-page">
        <div
          className="ftr-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "1.5fr 1fr 1fr 1fr",
            gap: 40,
            marginBottom: 48,
          }}
        >
          <div>
            <Logo />
            <p
              style={{
                fontSize: 14,
                color: "var(--text-dim)",
                maxWidth: 320,
                marginTop: 16,
                lineHeight: 1.5,
              }}
            >
              Премиум-стоки одной ссылкой. Без VPN, регистраций и подписок по $90/мес.
            </p>
          </div>

          <div>
            <div className="eyebrow" style={{ fontSize: 11, marginBottom: 16 }}>
              Продукт
            </div>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
              {PRODUCT.map(([label, href]) => (
                <li key={label}>
                  <Link href={href} style={{ fontSize: 14, color: "var(--text-dim)" }} className="nav-l">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <div className="eyebrow" style={{ fontSize: 11, marginBottom: 16 }}>
              Аккаунт
            </div>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
              {ACCOUNT.map(([label, href]) => (
                <li key={label}>
                  <Link href={href} style={{ fontSize: 14, color: "var(--text-dim)" }} className="nav-l">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <div className="eyebrow" style={{ fontSize: 11, marginBottom: 16 }}>
              Контакты
            </div>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
              {CONTACTS.map((c) => (
                <li key={c.label}>
                  <a
                    href={c.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="nav-l"
                    style={{ fontSize: 14, color: "var(--text-dim)", display: "inline-flex", alignItems: "center", gap: 10 }}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={c.logo}
                      alt=""
                      aria-hidden="true"
                      style={{
                        width: 22,
                        height: 22,
                        borderRadius: 6,
                        display: "block",
                        flexShrink: 0,
                        objectFit: "cover",
                        boxShadow: `0 0 0 1px rgba(255,255,255,0.08), 0 4px 14px -4px ${c.shadow}`,
                      }}
                    />
                    {c.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div
          className="footer-bottom"
          style={{
            paddingTop: 24,
            borderTop: "1px solid var(--border)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div className="mono" style={{ fontSize: 12, color: "var(--text-mute)" }}>
            © 2026 FootageHub. Сделано на одной зелёной лапке.
          </div>
          <div style={{ display: "flex", gap: 18, fontSize: 12, color: "var(--text-mute)" }}>
            <a href="/assets/public_offer_footagehub.pdf" target="_blank" rel="noopener noreferrer">
              Оферта
            </a>
            <a href="#">Политика</a>
            <a href="#">Правила</a>
          </div>
        </div>
      </div>
    </footer>
    </LocalizedContent>
  );
}
