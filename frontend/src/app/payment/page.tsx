"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getToken } from "@/lib/auth";
import Link from "next/link";
import { paymentsApi } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import { PageShell } from "@/components/page-shell";

type PlanRaw = { name?: string; price?: number; currency?: string };
type Plan = { key: string; name: string; price: number; currency: string };

const USD_PRICES: Record<string, number> = {
  monthly_50: 4.99,
  monthly_150: 10.99,
  monthly_400: 21.99,
};

function displayPrice(plan: Plan): string {
  const price = USD_PRICES[plan.key];
  return price === undefined ? `$${plan.price.toFixed(2)}` : `$${price.toFixed(2)}`;
}

function filesFor(key: string): string {
  if (key === "monthly_50") return "50 файлов / месяц";
  if (key === "monthly_150") return "150 файлов / месяц";
  if (key === "monthly_400") return "400 файлов / месяц";
  if (key === "daily_30") return "30 файлов / день";
  if (key === "unlimited") return "Безлимит";
  return "";
}

function PaymentPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedPlan = searchParams.get("plan");
  const submitting = useRef(false);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [tier, setTier] = useState<string>("");
  const [paying, setPaying] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    paymentsApi
      .plans()
      .then((res) => {
        const raw = res.data as Record<string, PlanRaw>;
        const list: Plan[] = Object.entries(raw).map(([key, p]) => ({
          key,
          name: p.name ?? key,
          price: p.price ?? 0,
          currency: p.currency ?? "USD",
        }));
        setPlans(list);
      })
      .catch(() => setError("Не удалось загрузить тарифы"))
      .finally(() => setLoading(false));
  }, []);

  const selected = useMemo(() => plans.find((p) => p.key === tier)
    ?? plans.find((p) => p.key === requestedPlan)
    ?? plans.find((p) => p.key === "monthly_150") ?? plans[0], [plans, tier, requestedPlan]);

  async function pay() {
    if (submitting.current) return;
    if (!selected) {
      setError("Выберите тариф");
      return;
    }
    if (!getToken()) {
      router.push(`/auth?redirect=${encodeURIComponent(`/payment?plan=${selected.key}`)}`);
      return;
    }
    submitting.current = true;
    setError("");
    setPaying(true);
    try {
      const res = await paymentsApi.create(selected.key, "webpay");
      window.location.href = res.data.invoice_url;
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || "Ошибка создания платежа");
      setPaying(false);
      submitting.current = false;
    }
  }

  return (
    <PageShell>
      <main style={{ padding: "40px 0 80px", position: "relative" }}>
        <div className="container-page" style={{ maxWidth: 1100 }}>
          <div style={{ marginBottom: 28 }}>
            <Link href="/dashboard" style={{ fontSize: 13, color: "var(--text-dim)" }}>
              ← назад в кабинет
            </Link>
            <h1 className="h-display" style={{ fontSize: 40, margin: "10px 0 6px", letterSpacing: "-0.03em" }}>
              Оплата тарифа
            </h1>
            <p style={{ fontSize: 16, color: "var(--text-dim)", margin: 0 }}>
              Списание разовое. Без автопродления. Включается мгновенно после оплаты.
            </p>
          </div>

          {loading ? (
            <div style={{ padding: 60, textAlign: "center", color: "var(--text-dim)" }}>Загрузка тарифов…</div>
          ) : (
            <div className="pay-grid" style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 20 }}>
              {/* Left: tier + method */}
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                <div className="card" style={{ padding: 24 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", marginBottom: 14, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    1 · Тариф
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {plans.map((p) => (
                      <button
                        key={p.key}
                        type="button"
                        disabled={paying}
                        aria-pressed={selected?.key === p.key}
                        onClick={() => { setTier(p.key); trackEvent("plan_selected", { plan: p.key }); }}
                        style={{
                          textAlign: "left",
                          padding: 18,
                          borderRadius: 14,
                          border: `1px solid ${selected?.key === p.key ? "var(--accent)" : "var(--border)"}`,
                          background: selected?.key === p.key ? "color-mix(in oklab, var(--accent) 8%, transparent)" : "var(--bg-soft)",
                          display: "flex",
                          alignItems: "center",
                          gap: 16,
                          transition: "all 0.15s",
                        }}
                      >
                        <div
                          style={{
                            width: 22,
                            height: 22,
                            borderRadius: 999,
                            border: `2px solid ${selected?.key === p.key ? "var(--accent)" : "var(--border-strong)"}`,
                            background: selected?.key === p.key ? "var(--accent)" : "transparent",
                            display: "grid",
                            placeItems: "center",
                            flexShrink: 0,
                          }}
                        >
                          {selected?.key === p.key && <span style={{ width: 8, height: 8, borderRadius: 999, background: "white" }} />}
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div className="flex items-center gap-2 flex-wrap" style={{ marginBottom: 4 }}>
                            <span style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.01em" }}>{p.name}</span>
                            {p.key === "monthly_150" && (
                              <span style={{ fontSize: 10, padding: "3px 8px", borderRadius: 999, background: "var(--accent)", color: "white", fontWeight: 600 }}>
                                ★ ПОПУЛЯРНЫЙ
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: 13, color: "var(--text-dim)" }}>{filesFor(p.key)}</div>
                        </div>
                        <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em" }}>{displayPrice(p)}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="card" style={{ padding: 24 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", marginBottom: 14, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    2 · Способ оплаты
                  </div>
                  <div
                    style={{
                      padding: 18,
                      borderRadius: 14,
                      border: "1px solid var(--accent)",
                      background: "color-mix(in oklab, var(--accent) 8%, transparent)",
                      display: "flex",
                      gap: 12,
                      alignItems: "center",
                    }}
                  >
                    <div style={{ fontSize: 24 }}>💳</div>
                    <div>
                      <div style={{ fontSize: 15, fontWeight: 600 }}>Карта</div>
                      <div style={{ fontSize: 12, color: "var(--text-dim)" }}>Visa / Mir / MC · WebPay</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right: summary */}
              <div className="card" data-testid="payment-summary" aria-live="polite" style={{ padding: 28, position: "sticky", top: 90, alignSelf: "start" }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", marginBottom: 18, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  Итого
                </div>
                <div style={{ paddingBottom: 16, borderBottom: "1px solid var(--border)", marginBottom: 16 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12, marginBottom: 8 }}>
                    <span style={{ fontSize: 14, color: "var(--text-dim)" }}>Тариф {selected?.name ?? "—"}</span>
                    <span style={{ fontSize: 14 }}>{selected ? displayPrice(selected) : "—"}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
                    <span style={{ fontSize: 14, color: "var(--text-dim)" }}>Объём</span>
                    <span className="mono" style={{ fontSize: 14, color: "var(--text-dim)" }}>{selected ? filesFor(selected.key) : "—"}</span>
                  </div>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12, marginBottom: 24 }}>
                  <span style={{ fontSize: 14 }}>К оплате</span>
                  <span style={{ fontSize: 32, fontWeight: 700, letterSpacing: "-0.03em", color: "var(--accent)" }}>
                    {selected ? displayPrice(selected) : "—"}
                  </span>
                </div>

                {error && <div style={{ fontSize: 13, color: "#FF6B6B", marginBottom: 12 }}>{error}</div>}

                <button
                  onClick={pay}
                  disabled={paying || !selected}
                  className="btn btn-primary"
                  style={{ width: "100%", padding: "16px 24px", fontSize: 15, marginBottom: 14, opacity: paying || !selected ? 0.7 : 1 }}
                >
                  {paying ? "Перенаправление…" : selected ? `Оплатить ${displayPrice(selected)}` : "Выберите тариф"}
                </button>

                <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 8 }}>
                  {["Все стоки: Envato, Freepik, Motion Array", "Доставка в Telegram за ~8 секунд"].map((p) => (
                    <li key={p} style={{ fontSize: 13, color: "var(--text-dim)", display: "flex", gap: 8 }}>
                      <span style={{ color: "var(--green)" }}>✓</span>
                      <span>{p}</span>
                    </li>
                  ))}
                </ul>

                <div style={{ fontSize: 11, color: "var(--text-mute)", marginTop: 18, lineHeight: 1.5 }}>
                  Нажимая «Оплатить», ты соглашаешься с офертой. Оплата проходит через защищённый шлюз провайдера.
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </PageShell>
  );
}

export default function PaymentPage() {
  return <Suspense fallback={<PageShell><main className="container-page">Загрузка тарифов…</main></PageShell>}><PaymentPageInner /></Suspense>;
}
