import Link from "next/link";
import { Logo } from "./brand";

/** Общая шапка для внутренних страниц (кабинет / оплата / AI / вход). */
export function PageShell({ children }: { children: React.ReactNode }) {
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
            <Link href="/" className="nav-l">
              ← На главную
            </Link>
          </nav>
        </div>
      </header>
      {children}
    </div>
  );
}
