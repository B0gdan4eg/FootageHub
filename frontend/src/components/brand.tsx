"use client";

import Link from "next/link";
import { useHomeHref } from "@/lib/language";

/** Основной акцент бренда (используется в инлайн-градиентах/тенях). */
export const ACCENT = "#2D6BFF";

/** Логотип FootageHub: лягушка-аватар + «footage·hub». */
export function Logo({ size = 38 }: { size?: number }) {
  const homeHref = useHomeHref();
  return (
    <Link href={homeHref} className="flex items-center gap-3" style={{ textDecoration: "none" }}>
      <div
        style={{
          width: size,
          height: size,
          borderRadius: 10,
          overflow: "hidden",
          boxShadow: `0 6px 20px -6px ${ACCENT}aa`,
          flexShrink: 0,
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/assets/frog-views.jpg"
          alt="FootageHub"
          style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
        />
      </div>
      <div style={{ display: "flex", flexDirection: "column", lineHeight: 0.95 }}>
        <span style={{ fontWeight: 700, fontSize: 18, letterSpacing: "-0.02em" }}>footage</span>
        <span style={{ fontWeight: 700, fontSize: 18, letterSpacing: "-0.02em", color: ACCENT }}>
          hub
        </span>
      </div>
    </Link>
  );
}
