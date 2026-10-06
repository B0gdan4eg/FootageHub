"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { LanguageSwitcher, useHomeHref, useLanguage } from "@/lib/language";
import { Logo } from "./brand";

/** Общая шапка для внутренних страниц (кабинет / оплата / AI / вход). */
export function PageShell({ children }: { children: React.ReactNode }) {
  const homeHref = useHomeHref();
  const { language } = useLanguage();
  const pathname = usePathname();
  const [menuPage, setMenuPage] = useState<string | null>(null);
  const menuOpen = menuPage === pathname;
  return (
    <div style={{ minHeight: "100vh", position: "relative" }}>
      <header
        style={{
          position: "sticky",
          top: 0,
          zIndex: 50,
          background: "color-mix(in oklab, var(--bg) 80%, transparent)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div className="container-page flex items-center justify-between" style={{ height: 68 }}>
          <Logo size={36} />
          <nav
            className="hidden md:flex items-center gap-8"
            style={{ fontSize: 14, color: "var(--text-dim)" }}
          >
            <Link href="/dashboard" className="nav-l">
              Кабинет
            </Link>
            <Link href="/payment" className="nav-l">
              Оплата
            </Link>
            <Link
              href="/ai"
              className="nav-l"
              style={{ display: "inline-flex", gap: 6, alignItems: "center" }}
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
            <Link href={homeHref} className="nav-l">
              ← На главную
            </Link>
          </nav>
          <div className="flex items-center gap-2">
            <LanguageSwitcher />
            <button type="button" className="md:hidden" data-no-translate
              aria-label={language === "en" ? (menuOpen ? "Close menu" : "Open menu") : (menuOpen ? "Закрыть меню" : "Открыть меню")}
              title={language === "en" ? "Menu" : "Меню"} aria-expanded={menuOpen} aria-controls="mobile-navigation"
              onClick={() => setMenuPage(menuOpen ? null : pathname)}
              style={{ width: 40, height: 40, alignItems: "center", justifyContent: "center" }}>
              {menuOpen ? <X size={22} /> : <Menu size={22} />}
            </button>
          </div>
        </div>
        {menuOpen && <nav id="mobile-navigation" className="flex flex-wrap md:hidden container-page" aria-label={language === "en" ? "Navigation" : "Навигация"}
          onKeyDown={event => { if (event.key === "Escape") setMenuPage(null); }}
          style={{ paddingTop: 8, paddingBottom: 16, gap: 16 }}>
          <Link onClick={() => setMenuPage(null)} href="/dashboard">Кабинет</Link>
          <Link onClick={() => setMenuPage(null)} href="/payment">Оплата</Link>
          <Link onClick={() => setMenuPage(null)} href="/ai">AI</Link>
          <Link onClick={() => setMenuPage(null)} href={homeHref}>На главную</Link>
        </nav>}
      </header>
      {children}
    </div>
  );
}
