import posthog from "posthog-js";

export type AnalyticsConsent = { statistics: boolean; replay: boolean; expires: number };
export type AnalyticsConfig = { ga4: string; posthog: string; posthogHost: string };
export const CONSENT_KEY = "fh_analytics_consent_v2";
export const CONSENT_LIFETIME = 180 * 24 * 60 * 60 * 1000;
const ORIGIN = "https://envato-freepik-download.store";
const PAGES: Record<string, string> = {
  "/": "Home", "/en": "Home EN", "/auth": "Sign in",
  "/dashboard": "Dashboard", "/download": "Download", "/payment": "Payment", "/ai": "AI",
};
type Tag = (...args: unknown[]) => void;
declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: Tag;
  }
}

let consent: AnalyticsConsent | null = null;
let config: AnalyticsConfig = { ga4: "", posthog: "", posthogHost: "https://eu.i.posthog.com" };
let gaStarted = false;
let replayStarted = false;
let posthogStarted = false;
let lastPosthogPage = "";
let lastPage = "";

export function readConsent(): AnalyticsConsent | null {
  try {
    const value = JSON.parse(localStorage.getItem(CONSENT_KEY) || "null");
    if (typeof value?.statistics === "boolean" && typeof value?.replay === "boolean"
      && typeof value?.expires === "number" && value.expires > Date.now()
      && value.expires <= Date.now() + CONSENT_LIFETIME + 60000) return value;
  } catch { /* Storage can be disabled by the browser. */ }
  return null;
}

export function pageFields(path: string, referrer = "") {
  if (!Object.hasOwn(PAGES, path)) return null;
  let origin = "";
  try { origin = new URL(referrer).origin; } catch { /* No referrer. */ }
  return { page_location: ORIGIN + path, page_title: "FootageHub | " + PAGES[path], page_referrer: origin };
}

export function assetProvider(url: string) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    for (const [domain, provider] of [["freepik.com", "freepik"], ["magnific.com", "freepik"],
      ["envato.com", "envato"], ["motionarray.com", "motion_array"]]) {
      if (host === domain || host.endsWith("." + domain)) return provider;
    }
  } catch { /* Invalid links are reported only as an unknown provider. */ }
  return "unknown";
}

export function safePlan(key: string) {
  return ["monthly_50", "monthly_150", "monthly_400", "daily_30", "unlimited"].includes(key) ? key : "other";
}

function allowed() {
  return !!consent?.statistics && consent.expires > Date.now() && (gaStarted || posthogStarted);
}

type EventName = "login" | "navigation_click" | "plan_selected" | "begin_checkout" |
  "payment_redirect" | "checkout_error" | "download_requested" | "download_link_ready" | "download_error" |
  "registration_started" | "registration_qr_ready" | "registration_telegram_opened" |
  "registration_completed" | "registration_failed" | "payment_page_viewed" | "payment_cancelled";
type EventDetails = { provider?: string; plan?: string; destination?: string; duration_ms?: number; reason?: string };

export function checkoutAnalyticsId(): string | undefined {
  try {
    if (!allowed() || !posthogStarted) return;
    const id = posthog.get_distinct_id();
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id) ? id : undefined;
  } catch { return; }
}

export function trackEvent(name: EventName, details: EventDetails = {}) {
  try {
    if (typeof window === "undefined" || !allowed()) return;
    const fields = pageFields(window.location.pathname, document.referrer);
    if (!fields) return;
    const safe: Record<string, string | number> = {};
    if (details.provider && ["freepik", "envato", "motion_array", "unknown", "webpay", "cryptobot"].includes(details.provider)) safe.provider = details.provider;
    if (details.plan) safe.plan = safePlan(details.plan);
    if (details.destination && ["auth", "dashboard", "payment", "ai", "home", "pricing", "telegram_bot", "telegram_channel", "telegram_support"].includes(details.destination)) safe.destination = details.destination;
    if (Number.isFinite(details.duration_ms)) safe.duration_ms = Math.max(0, Math.min(3600000, Math.round(details.duration_ms!)));
    if (name === "login") safe.method = "telegram_qr";
    if (name.startsWith("registration_")) safe.method = "telegram_qr";
    if (details.reason && ["session_creation", "expired", "rejected", "consumed", "plans_load"].includes(details.reason)) safe.reason = details.reason;
    if (gaStarted) window.gtag?.("event", name, { ...fields, ...safe, send_to: config.ga4 });
    if (posthogStarted) posthog.capture(name, { ...fields, ...safe });
    return true;
  } catch { /* Analytics must never interrupt auth, checkout or downloads. */ }
}

function appendScript(id: string, src: string) {
  if (document.getElementById(id)) return;
  const script = document.createElement("script");
  script.id = id;
  script.async = true;
  script.referrerPolicy = "no-referrer";
  script.src = src;
  document.head.appendChild(script);
}

export function syncAnalytics(nextConfig: AnalyticsConfig, nextConsent: AnalyticsConsent | null, path: string) {
  config = nextConfig;
  consent = nextConsent;
  if (!consent || consent.expires <= Date.now()) return;
  const fields = pageFields(path, document.referrer);
  if (gaStarted) (window as unknown as Record<string, unknown>)["ga-disable-" + config.ga4] = !fields;
  if (!fields) lastPage = "";
  if (consent.statistics && /^G-[A-Z0-9]+$/.test(config.ga4) && fields) {
    if (!gaStarted) {
      window.dataLayer = window.dataLayer || [];
      // Google's queue requires the standard gtag arguments object.
      // eslint-disable-next-line prefer-rest-params
      window.gtag = function () { window.dataLayer!.push(arguments); };
      window.gtag("consent", "default", {
        analytics_storage: "granted", ad_storage: "denied",
        ad_user_data: "denied", ad_personalization: "denied",
      });
      window.gtag("js", new Date());
      window.gtag("config", config.ga4, {
        ...fields, send_page_view: false, allow_google_signals: false,
        allow_ad_personalization_signals: false, cookie_flags: "SameSite=Lax;Secure",
      });
      appendScript("fh-ga4", "https://www.googletagmanager.com/gtag/js?id=" + config.ga4);
      gaStarted = true;
    }
    if (lastPage !== path) {
      window.gtag?.("set", fields);
      window.gtag?.("event", "page_view", { ...fields, send_to: config.ga4 });
      lastPage = path;
    }
  }
  const replayAllowed = consent.replay && isPublicPage(path)
    && !window.location.search && !window.location.hash;
  if (/^phc_[A-Za-z0-9_-]+$/.test(config.posthog) && fields
    && (consent.statistics || replayAllowed)) {
    if (!posthogStarted) {
      posthog.init(config.posthog, {
        api_host: config.posthogHost,
        autocapture: false, capture_pageview: false, capture_pageleave: false,
        capture_performance: false, disable_session_recording: true,
        enable_recording_console_log: false, disable_surveys: true,
        person_profiles: "never", persistence: "localStorage",
        advanced_disable_feature_flags: true,
        capture_exceptions: false,
        save_campaign_params: false, save_referrer: false,
        session_recording: {
          maskAllInputs: true, maskTextSelector: "*", blockSelector: "[data-ph-block]",
          recordHeaders: false, recordBody: false,
        },
        before_send: event => {
          if (!consent || consent.expires <= Date.now()) return null;
          const replay = event?.event === "$snapshot";
          if (replay ? !consent.replay || !isPublicPage(window.location.pathname)
            || !!window.location.search || !!window.location.hash : !consent.statistics) return null;
          if (event?.properties) {
            const safeFields = pageFields(window.location.pathname, document.referrer);
            if (!safeFields) return null;
            event.properties.$current_url = safeFields.page_location;
            event.properties.$pathname = window.location.pathname;
            event.properties.$referrer = safeFields.page_referrer;
            delete event.properties.$search;
            delete event.properties.$hash;
            for (const key of Object.keys(event.properties)) {
              if (key.startsWith("$initial_") || key.startsWith("utm_")
                || ["gclid", "fbclid", "msclkid"].includes(key)) delete event.properties[key];
            }
          }
          return event;
        },
      });
      posthogStarted = true;
    }
    if (consent.statistics && lastPosthogPage !== path) {
      posthog.capture("$pageview", fields);
      if (path === "/auth") trackEvent("registration_started");
      if (path === "/payment") trackEvent("payment_page_viewed");
      lastPosthogPage = path;
      window.dispatchEvent?.(new Event("fh-analytics-ready"));
    }
    if (replayAllowed && !replayStarted) {
      posthog.startSessionRecording();
      replayStarted = true;
    }
  }
  if (!fields) lastPosthogPage = "";
  if (!replayAllowed) stopReplay();
}

export function isPublicPage(path: string) { return path === "/" || path === "/en"; }

export function stopReplay() {
  if (replayStarted) {
    try { posthog.stopSessionRecording(); replayStarted = false; } catch { /* Vendor may be blocked. */ }
  }
}

export function saveConsent(statistics: boolean, replay: boolean) {
  const next = { statistics, replay, expires: Date.now() + CONSENT_LIFETIME };
  try { localStorage.setItem(CONSENT_KEY, JSON.stringify(next)); } catch { /* Session-only choice. */ }
  const needsReload = (gaStarted && !!consent?.statistics && !statistics)
    || (posthogStarted && ((!!consent?.statistics && !statistics) || (!!consent?.replay && !replay)));
  consent = next;
  if (needsReload) {
    // Unload vendor listeners completely when permission is withdrawn.
    if (config.ga4) (window as unknown as Record<string, unknown>)["ga-disable-" + config.ga4] = true;
    stopReplay();
    if (posthogStarted) posthog.opt_out_capturing();
    clearAnalyticsCookies();
    window.location.reload();
  }
  return next;
}

function clearAnalyticsCookies() {
  try {
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const key = localStorage.key(i);
      if (key?.startsWith("ph_") || key?.startsWith("__ph_opt_in_out_")) localStorage.removeItem(key);
    }
  } catch { /* Storage may be unavailable. */ }
  for (const cookie of document.cookie.split(";")) {
    const name = cookie.split("=")[0].trim();
    if (!/^(_ga($|_)|_clck$|_clsk$|ph_)/.test(name)) continue;
    const labels = location.hostname.split(".");
    const domains = ["", ...labels.map((_, i) => "; Domain=" + labels.slice(i).join("."))];
    for (const domain of domains) document.cookie = name + "=; Max-Age=0; Path=/" + domain;
  }
}

export function handleAnalyticsClick(event: MouseEvent) {
  const element = event.target instanceof Element ? event.target.closest("a[href]") : null;
  if (!(element instanceof HTMLAnchorElement)) return;
  const url = new URL(element.href, location.href);
  const destinations: Record<string, string> = {
    "/": "home", "/en": "home", "/auth": "auth", "/dashboard": "dashboard", "/payment": "payment", "/ai": "ai",
  };
  const telegram: Record<string, string> = {
    "/footagehub_bot": "telegram_bot", "/footagehub_channel": "telegram_channel", "/footagehub_support": "telegram_support",
  };
  const destination = url.origin === location.origin
    ? (url.hash === "#pricing" ? "pricing" : destinations[url.pathname])
    : url.hostname === "t.me" ? telegram[url.pathname.toLowerCase()] : undefined;
  if (destination) trackEvent("navigation_click", { destination });
  // A full navigation discards the replay SDK before private content can render.
  if (replayStarted && url.origin === location.origin && !isPublicPage(url.pathname)
    && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey
    && event.button === 0 && element.target !== "_blank" && !element.hasAttribute("download")) {
    event.preventDefault();
    event.stopImmediatePropagation();
    stopReplay();
    window.location.assign(url.href);
  }
}
