"use client";

import { useEffect, useLayoutEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Cookie, X } from "lucide-react";
import { useLanguage } from "@/lib/language";
import {
  type AnalyticsConfig, type AnalyticsConsent, CONSENT_KEY, handleAnalyticsClick,
  isPublicPage, readConsent, saveConsent, stopReplay, syncAnalytics,
} from "@/lib/analytics";
import styles from "./analytics-consent.module.css";

export function AnalyticsConsentBanner() {
  const pathname = usePathname();
  const { language } = useLanguage();
  const en = pathname === "/en" || language === "en";
  const [config, setConfig] = useState<AnalyticsConfig | null>(null);
  const [consent, setConsent] = useState<AnalyticsConsent | null>(null);
  const [open, setOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [statistics, setStatistics] = useState(false);
  const [replay, setReplay] = useState(false);

  useEffect(() => {
    const abort = new AbortController();
    fetch("/analytics-config", { signal: abort.signal, cache: "no-store" })
      .then(response => response.ok ? response.json() : null)
      .then((value: AnalyticsConfig | null) => {
        if (!value || (!value.ga4 && !value.posthog)) return;
        const saved = readConsent();
        setConfig(value);
        setConsent(saved);
        setStatistics(saved?.statistics ?? !!(value.ga4 || value.posthog));
        setReplay(saved?.replay ?? !!value.posthog);
        setOpen(!saved);
      }).catch(() => { /* No analytics if config is unavailable. */ });
    return () => abort.abort();
  }, []);

  useLayoutEffect(() => {
    if (!isPublicPage(pathname)) stopReplay();
    if (config) syncAnalytics(config, consent, pathname);
  }, [config, consent, pathname]);

  useEffect(() => {
    const storage = (event: StorageEvent) => {
      if (event.key === CONSENT_KEY || event.key === null) window.location.reload();
    };
    document.addEventListener("click", handleAnalyticsClick, true);
    window.addEventListener("storage", storage);
    return () => {
      document.removeEventListener("click", handleAnalyticsClick, true);
      window.removeEventListener("storage", storage);
    };
  }, []);

  useEffect(() => {
    if (!consent) return;
    const timer = window.setInterval(() => {
      if (consent.expires <= Date.now()) {
        stopReplay();
        window.location.reload();
      }
    }, 60000);
    return () => window.clearInterval(timer);
  }, [consent]);

  function choose(stats: boolean, recordings: boolean) {
    setConsent(saveConsent(stats, recordings));
    setStatistics(stats);
    setReplay(recordings);
    setSettingsOpen(false);
    setOpen(false);
  }

  if (!config) return null;
  const title = en ? "Privacy preferences" : "Настройки конфиденциальности";
  return (
    <div data-no-translate data-ph-block="true" className={styles.root}>
      {open ? (
        <section className={styles.panel} aria-label={title}>
          <div className={styles.heading}>
            <h2>{title}</h2>
            {consent && <button className={styles.icon} type="button" onClick={() => setOpen(false)} aria-label={en ? "Close" : "Закрыть"}><X size={20} /></button>}
          </div>
          <p>{en
            ? "With your permission, PostHog and optional Google Analytics measure visits and actions, and PostHog records clicks and masked sessions on the home page. Optional cookies help improve the site. Sign-in and payment work without them."
            : "С вашего разрешения PostHog и необязательный Google Analytics собирают статистику посещений и действий, а PostHog записывает клики и сессии на главной со скрытым текстом. Необязательные cookies помогают улучшать сайт. Вход и оплата работают без них."}</p>
          <div id="analytics-options" className={styles.options} hidden={!settingsOpen}>
            {(config.ga4 || config.posthog) && <label><input type="checkbox" checked={statistics} onChange={e => setStatistics(e.target.checked)} />{en ? "Visit and usage statistics" : "Статистика посещений и действий"}</label>}
            {config.posthog && <label><input type="checkbox" checked={replay} onChange={e => setReplay(e.target.checked)} />{en ? "Home page recordings (PostHog)" : "Запись главной страницы (PostHog)"}</label>}
          </div>
          <div className={styles.links}>
            <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">{en ? "Google privacy" : "Конфиденциальность Google"}</a>
            <a href="https://posthog.com/privacy" target="_blank" rel="noopener noreferrer">{en ? "PostHog privacy" : "Конфиденциальность PostHog"}</a>
          </div>
          <div className={styles.actions}>
            <button type="button" onClick={() => choose(settingsOpen ? statistics : !!(config.ga4 || config.posthog), settingsOpen ? replay : !!config.posthog)}>{en ? "Accept" : "Принять"}</button>
            <button type="button" onClick={() => choose(false, false)}>{en ? "Reject" : "Отклонить"}</button>
            <button type="button" aria-expanded={settingsOpen} aria-controls="analytics-options" onClick={() => setSettingsOpen(!settingsOpen)}>{en ? "Customize" : "Настроить"}</button>
          </div>
        </section>
      ) : (
        <button className={`${styles.icon} ${styles.reopen}`} type="button" title={title} aria-label={title} onClick={() => {
          setStatistics(consent?.statistics ?? false);
          setReplay(consent?.replay ?? false);
          setSettingsOpen(false);
          setOpen(true);
        }}><Cookie size={21} /></button>
      )}
    </div>
  );
}
