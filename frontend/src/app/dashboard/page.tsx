"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { usersApi, downloadsApi, type User } from "@/lib/api";
import { PageShell } from "@/components/page-shell";
import { ACCENT } from "@/components/brand";

interface DownloadItem {
  id: number;
  url: string;
  service_type: string | null;
  downloaded_at: string | null;
}

interface SubscriptionItem {
  id: number;
  subscription_type: string;
  service_type: string;
  used_total: number;
  total_limit: number | null;
  used_today: number;
  daily_limit: number | null;
  end_date: string;
  is_active: boolean;
}

const PLAN_NAMES: Record<string, string> = {
  MONTHLY_50: "Lite",
  MONTHLY_150: "Standard",
  MONTHLY_400: "Pro",
  DAILY_30: "Daily 30",
  UNLIMITED: "Unlimited",
  CUSTOM: "Custom",
};

const SOURCE_LABELS: Record<string, string> = {
  ENVATO: "Envato",
  FREEPIK: "Freepik",
  MOTION_ARRAY: "Motion Array",
};

function sourceColor(s: string | null): string {
  if (s === "ENVATO") return "var(--green)";
  if (s === "FREEPIK") return "#1273EB";
  if (s === "MOTION_ARRAY") return "#FFA82E";
  return "var(--text-dim)";
}

function sourceBg(s: string | null): string {
  if (s === "ENVATO") return "rgba(0,224,97,0.12)";
  if (s === "FREEPIK") return "rgba(18,115,235,0.15)";
  if (s === "MOTION_ARRAY") return "rgba(255,168,46,0.15)";
  return "var(--border)";
}

function fileName(url: string): string {
  try {
    const clean = url.split("?")[0].replace(/\/$/, "");
    const seg = decodeURIComponent(clean.split("/").pop() || url);
    return seg.length > 2 ? seg : url;
  } catch {
    return url;
  }
}

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso).getTime();
  const diff = Math.max(0, Date.now() - d);
  const min = Math.floor(diff / 60000);
  if (min < 1) return "только что";
  if (min < 60) return `${min} мин назад`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} ч назад`;
  const days = Math.floor(h / 24);
  if (days < 7) return `${days} дн назад`;
  return new Date(iso).toLocaleDateString("ru-RU");
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [subs, setSubs] = useState<SubscriptionItem[]>([]);
  const [history, setHistory] = useState<DownloadItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [url, setUrl] = useState("");
  const [stage, setStage] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [dlError, setDlError] = useState("");

  const loadData = useCallback(async () => {
    const [profileRes, dlRes, subsRes] = await Promise.all([
      usersApi.profile(),
      usersApi.downloads(1),
      usersApi.subscriptions(),
    ]);
    setUser(profileRes.data);
    setHistory(((dlRes.data as { items?: DownloadItem[] }).items ?? []).slice(0, 12));
    setSubs((subsRes.data as SubscriptionItem[]) ?? []);
  }, []);

  useEffect(() => {
    loadData()
      .catch(() => router.push("/auth"))
      .finally(() => setLoading(false));
  }, [loadData, router]);

  async function submit(e?: React.FormEvent) {
    e?.preventDefault();
    if (!url.trim()) return;
    setStage("loading");
    setDlError("");
    try {
      const res = await downloadsApi.download(url.trim());
      setStage("ok");
      if (res.data?.download_url) {
        window.open(res.data.download_url, "_blank", "noopener,noreferrer");
      }
      setUrl("");
      // обновляем историю/остаток
      loadData().catch(() => {});
      setTimeout(() => setStage("idle"), 2500);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setDlError(err.response?.data?.detail || "Не удалось получить файл");
      setStage("error");
      setTimeout(() => setStage("idle"), 4000);
    }
  }

  if (loading) {
    return (
      <PageShell>
        <div style={{ minHeight: "60vh", display: "grid", placeItems: "center", color: "var(--text-dim)" }}>
          Загрузка…
        </div>
      </PageShell>
    );
  }

  const activeSub = subs[0];
  const planName = activeSub ? PLAN_NAMES[activeSub.subscription_type] ?? activeSub.subscription_type : null;
  const total = activeSub?.total_limit ?? null;
  const left = total != null ? Math.max(0, total - (activeSub?.used_total ?? 0)) : (user?.credits ?? 0);
  const usedThisMonth = activeSub?.used_total ?? 0;
  const handle = user?.username && !["ru", "en"].includes(user.username) ? user.username : null;

  return (
    <PageShell>
      <main style={{ padding: "40px 0 80px", position: "relative" }}>
        <div className="container-page">
          {/* Header row */}
          <div className="flex items-center justify-between" style={{ marginBottom: 28, flexWrap: "wrap", gap: 16 }}>
            <div>
              <div className="eyebrow" style={{ marginBottom: 8 }}>Личный кабинет</div>
              <h1 className="h-display" style={{ fontSize: 40, margin: 0, letterSpacing: "-0.03em" }}>
                Привет{handle ? ", " : ""}
                {handle ? <span style={{ color: ACCENT }}>@{handle}</span> : " 👋"}
              </h1>
            </div>
            <div className="flex items-center gap-3">
              <div
                style={{
                  padding: "8px 14px",
                  borderRadius: 999,
                  background: "rgba(0, 224, 97, 0.12)",
                  color: "var(--green)",
                  fontSize: 13,
                  fontWeight: 500,
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                }}
              >
                <span style={{ width: 8, height: 8, borderRadius: 999, background: "var(--green)" }} />
                {activeSub
                  ? `${planName} · до ${new Date(activeSub.end_date).toLocaleDateString("ru-RU")}`
                  : "Free · бесплатные кредиты"}
              </div>
              <Link href="/payment" className="btn btn-ghost" style={{ padding: "10px 18px", fontSize: 13 }}>
                Сменить тариф
              </Link>
            </div>
          </div>

          {/* Paster + quota */}
          <div className="dash-grid" style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, marginBottom: 24 }}>
            <div className="card" style={{ padding: 28 }}>
              <div className="flex items-center justify-between" style={{ marginBottom: 18 }}>
                <h2 style={{ margin: 0, fontSize: 18, letterSpacing: "-0.01em" }}>Получить файл</h2>
                <span className="mono" style={{ fontSize: 11, color: "var(--text-mute)" }}>1 ссылка = 1 файл</span>
              </div>
              <form
                onSubmit={submit}
                style={{
                  display: "flex",
                  gap: 10,
                  padding: 8,
                  background: "var(--bg-soft)",
                  border: "1px solid",
                  borderColor: stage === "ok" ? "var(--green)" : "var(--border)",
                  borderRadius: 14,
                  alignItems: "center",
                  transition: "border-color 0.3s",
                  marginBottom: 14,
                }}
              >
                <span style={{ padding: "0 4px 0 8px", color: "var(--text-mute)", fontFamily: "var(--font-geist-mono), monospace", fontSize: 13 }}>→</span>
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://elements.envato.com/..."
                  style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: "var(--text)", fontFamily: "var(--font-geist-mono), monospace", fontSize: 14, padding: "10px 0" }}
                />
                <button type="submit" disabled={stage === "loading"} className="btn btn-primary" style={{ padding: "10px 20px", fontSize: 13, opacity: stage === "loading" ? 0.7 : 1 }}>
                  {stage === "loading" ? "Качаем…" : stage === "ok" ? "✓ Готово" : "Получить"}
                </button>
              </form>
              {stage === "error" && dlError && (
                <div style={{ fontSize: 13, color: "#FF6B6B", marginBottom: 10 }}>{dlError}</div>
              )}
              <div className="flex items-center gap-3" style={{ flexWrap: "wrap", fontSize: 12, color: "var(--text-dim)" }}>
                <span>Поддерживаем:</span>
                <span className="pill" style={{ padding: "4px 10px", fontSize: 11 }}><span className="dot" />Envato</span>
                <span className="pill" style={{ padding: "4px 10px", fontSize: 11 }}><span className="dot" />Freepik</span>
                <span className="pill warn" style={{ padding: "4px 10px", fontSize: 11 }}><span className="dot" />Motion Array (тех.работы)</span>
              </div>
            </div>

            <div className="card" style={{ padding: 28 }}>
              <div style={{ fontSize: 11, color: "var(--text-mute)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8 }}>Остаток</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 14 }}>
                <div style={{ fontSize: 48, fontWeight: 700, letterSpacing: "-0.04em", lineHeight: 1, color: "var(--accent)" }}>{left}</div>
                <div style={{ fontSize: 16, color: "var(--text-dim)" }}>{total != null ? `/ ${total} файлов` : "кредитов"}</div>
              </div>
              {total != null && (
                <div style={{ height: 8, background: "var(--border)", borderRadius: 999, overflow: "hidden", marginBottom: 12 }}>
                  <div style={{ height: "100%", width: `${Math.min(100, (left / total) * 100)}%`, background: "var(--accent)", borderRadius: 999, transition: "width 0.4s" }} />
                </div>
              )}
              <div style={{ fontSize: 12, color: "var(--text-dim)" }}>
                {activeSub ? `Сбросится ${new Date(activeSub.end_date).toLocaleDateString("ru-RU")}` : "Пополни баланс на странице оплаты"}
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="flex" style={{ gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
            <Stat label="Всего скачано" value={String(usedThisMonth)} sub="по подписке" />
            <Stat label="В этом месяце" value={String(usedThisMonth)} sub={total != null ? `из ${total}` : "—"} />
            <Stat label="Скорость" value="~8 сек" sub="среднее время выдачи" />
            <Stat label="Бесплатно" value={String(user?.credits ?? 0)} sub="кредитов на счету" accent="var(--green)" />
          </div>

          {/* History */}
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            <div className="flex items-center justify-between" style={{ padding: "20px 28px", borderBottom: "1px solid var(--border)" }}>
              <h2 style={{ margin: 0, fontSize: 18, letterSpacing: "-0.01em" }}>История скачиваний</h2>
            </div>
            {history.length === 0 ? (
              <div style={{ padding: 40, textAlign: "center", color: "var(--text-dim)", fontSize: 14 }}>
                Скачиваний пока нет — вставь ссылку выше.
              </div>
            ) : (
              <div>
                {history.map((f, i) => {
                  const label = SOURCE_LABELS[f.service_type ?? ""] ?? "—";
                  return (
                    <div
                      key={f.id}
                      className="hist-row"
                      style={{
                        display: "grid",
                        gridTemplateColumns: "40px 2fr 1fr 1fr auto",
                        gap: 16,
                        alignItems: "center",
                        padding: "16px 28px",
                        borderBottom: i < history.length - 1 ? "1px solid var(--border)" : "none",
                      }}
                    >
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: 8,
                          background: sourceBg(f.service_type),
                          color: sourceColor(f.service_type),
                          display: "grid",
                          placeItems: "center",
                          fontSize: 14,
                          fontWeight: 700,
                        }}
                      >
                        {label[0]}
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 14, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {fileName(f.url)}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-dim)" }}>{label}</div>
                      </div>
                      <div style={{ fontSize: 12, color: "var(--text-dim)" }}>{timeAgo(f.downloaded_at)}</div>
                      <div>
                        <span style={{ fontSize: 12, color: "var(--green)", display: "inline-flex", alignItems: "center", gap: 6 }}>
                          <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--green)" }} /> готов
                        </span>
                      </div>
                      <a href={f.url} target="_blank" rel="noopener noreferrer" className="btn btn-ghost" style={{ padding: "8px 14px", fontSize: 12 }}>
                        Открыть
                      </a>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </main>
    </PageShell>
  );
}

function Stat({ label, value, sub, accent }: { label: string; value: string; sub: string; accent?: string }) {
  return (
    <div style={{ padding: 20, borderRadius: 14, background: "var(--bg-soft)", border: "1px solid var(--border)", flex: 1, minWidth: 180 }}>
      <div style={{ fontSize: 11, color: "var(--text-mute)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: "-0.03em", color: accent || "var(--text)" }}>{value}</div>
      <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4 }}>{sub}</div>
    </div>
  );
}
