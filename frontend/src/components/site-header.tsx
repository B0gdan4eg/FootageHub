"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Logo } from "./brand";

const NAV = [
  { href: "#how", label: "Как работает" },
  { href: "#sources", label: "Стоки" },
  { href: "#pricing", label: "Тарифы" },
  { href: "#vs", label: "Сравнение" },
  { href: "#faq", label: "FAQ" },
];

/** Шапка лендинга: липкая, с блюром при скролле. */
export function SiteHeader() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        backdropFilter: scrolled ? "blur(20px)" : "none",
        WebkitBackdropFilter: scrolled ? "blur(20px)" : "none",
        background: scrolled ? "color-mix(in oklab, var(--bg) 70%, transparent)" : "transparent",
        borderBottom: scrolled ? "1px solid var(--border)" : "1px solid transparent",
        transition: "all 0.2s ease",
      }}
    >
      <div className="container-page flex items-center justify-between" style={{ height: 72 }}>
        <Logo />
        <nav
          className="hidden lg:flex items-center gap-8"
          style={{ fontSize: 14, color: "var(--text-dim)" }}
        >
          {NAV.map((n) => (
            <a key={n.href} href={n.href} className="nav-l">
              {n.label}
            </a>
          ))}
          <Link
            href="/ai"
            className="nav-l"
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            AI{" "}
            <span
              style={{
                fontSize: 10,
                padding: "2px 6px",
                borderRadius: 999,
                background: "var(--pink)",
                color: "white",
                fontWeight: 600,
              }}
            >
              SOON
            </span>
          </Link>
        </nav>
        <div className="flex items-center gap-3">
          <Link href="/auth" className="btn btn-ghost" style={{ padding: "10px 18px", fontSize: 14 }}>
            Войти
          </Link>
          <Link
            href="/auth"
            className="btn btn-primary"
            style={{ padding: "10px 18px", fontSize: 14 }}
          >
            Попробовать
          </Link>
        </div>
      </div>
    </header>
  );
}
