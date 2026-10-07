/* eslint-disable @typescript-eslint/no-require-imports -- Node's CommonJS test harness. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");
const path = require("node:path");

function harness() {
  const scripts = [];
  let stored = null;
  let reloads = 0;
  const location = { pathname: "/", search: "", hash: "", hostname: "example.com", reload: () => reloads++ };
  const document = {
    referrer: "https://search.example/private?token=SECRET", cookie: "access_token=KEEP; _ga=REMOVE",
    getElementById: id => scripts.find(s => s.id === id),
    createElement: () => ({}), head: { appendChild: script => scripts.push(script) },
  };
  const window = { location };
  const captures = [];
  let options;
  let recording = false;
  const posthog = {
    init: (_, config) => { options = config; },
    capture: (event, properties) => {
      const value = options.before_send({ event, properties: { ...properties, $current_url: "SECRET", $initial_current_url: "SECRET", utm_source: "SECRET" } });
      if (value) captures.push(value);
    },
    startSessionRecording: () => { recording = true; },
    stopSessionRecording: () => { recording = false; },
    opt_out_capturing: () => {},
  };
  const exports = {};
  const context = vm.createContext({ require: () => ({ default: posthog }), exports, window, document, location, URL, Date,
    localStorage: { getItem: () => stored, setItem: (_, value) => { stored = value; } },
  });
  const source = fs.readFileSync(path.join(__dirname, "../src/lib/analytics.ts"), "utf8");
  vm.runInContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, context);
  return { api: exports, window, scripts, location, captures, recording: () => recording, options: () => options, reloads: () => reloads, stored: value => { stored = value; } };
}
const config = { ga4: "G-TEST123456", posthog: "phc_test123", posthogHost: "https://eu.i.posthog.com" };
const choice = (statistics, replay) => ({ statistics, replay, expires: Date.now() + 100000 });
const events = h => (h.window.dataLayer || []).map(args => Array.from(args)).filter(args => args[0] === "event");

test("no vendor scripts or events without permission", () => {
  const h = harness();
  for (const consent of [null, choice(false, false), { ...choice(true, true), expires: 1 }]) h.api.syncAnalytics(config, consent, "/");
  h.api.trackEvent("login");
  assert.equal(h.scripts.length, 0);
  assert.equal(events(h).length, 0);
});

test("separate permissions, script deduplication and one view per navigation", () => {
  const h = harness();
  h.api.syncAnalytics(config, choice(true, false), "/");
  h.api.syncAnalytics(config, choice(true, false), "/");
  h.api.syncAnalytics(config, choice(true, false), "/payment");
  h.api.syncAnalytics(config, choice(true, false), "/");
  assert.equal(h.scripts.length, 1);
  assert.equal(events(h).filter(e => e[1] === "page_view").length, 3);
  assert.equal(h.scripts[0].referrerPolicy, "no-referrer");
  assert.equal(JSON.stringify(h.window.dataLayer).includes("SECRET"), false);
});

test("PostHog replay is only started on a clean public URL", () => {
  for (const pathname of ["/auth", "/dashboard", "/payment", "/ai", "/download", "/admin"]) {
    const h = harness();
    h.api.syncAnalytics(config, choice(false, true), pathname);
    assert.equal(h.scripts.length, 0);
  }
  for (const field of ["search", "hash"]) {
    const h = harness();
    h.location[field] = "?token=SECRET";
    h.api.syncAnalytics(config, choice(false, true), "/");
    assert.equal(h.scripts.length, 0);
  }
  const h = harness();
  h.api.syncAnalytics(config, choice(false, true), "/en");
  assert.equal(h.scripts.length, 0);
  assert.equal(h.recording(), true);
  assert.equal(h.captures.length, 0);
  assert.equal(events(h).length, 0);
});

test("events exclude arbitrary strings, asset URLs, and dynamic pages", () => {
  const h = harness();
  h.api.syncAnalytics(config, choice(true, false), "/");
  h.location.pathname = "/download";
  h.api.trackEvent("download_error", { provider: "SECRET", plan: "SECRET", destination: "SECRET", duration_ms: Infinity, url: "SECRET" });
  assert.equal(JSON.stringify(events(h)).includes("SECRET"), false);
  assert.equal(h.api.pageFields("/admin/user/123"), null);
  assert.equal(h.api.assetProvider("https://freepik.com.evil.test/file"), "unknown");
  assert.equal(h.api.assetProvider("https://ru.freepik.com/file?token=SECRET"), "freepik");
  assert.equal(h.api.assetProvider("https://elements.envato.com/asset"), "envato");
});

test("withdrawal disables Google and reloads once, reload does not loop", () => {
  const h = harness();
  h.api.syncAnalytics(config, choice(true, true), "/");
  h.api.saveConsent(false, false);
  assert.equal(h.reloads(), 1);
  assert.equal(h.window["ga-disable-G-TEST123456"], true);
  const count = events(h).length;
  h.api.trackEvent("login");
  assert.equal(events(h).length, count);
  const fresh = harness();
  fresh.api.syncAnalytics(config, choice(false, false), "/");
  assert.equal(fresh.reloads(), 0);
  assert.equal(fresh.scripts.length, 0);
});

test("malformed, expired and missing preferences default to no consent", () => {
  const h = harness();
  for (const value of [null, "invalid", "{}", JSON.stringify({ statistics: "true", replay: true, expires: Date.now() + 10000 }), JSON.stringify({ ...choice(true, true), expires: 1 })]) {
    h.stored(value);
    assert.equal(h.api.readConsent(), null);
  }
  h.stored(JSON.stringify(choice(true, false)));
  assert.equal(h.api.readConsent().statistics, true);
});


test("PostHog works without GA, filters metadata and honors separate replay consent", () => {
  const h = harness();
  h.api.syncAnalytics({ ...config, ga4: "" }, choice(true, false), "/");
  h.api.syncAnalytics({ ...config, ga4: "" }, choice(true, false), "/");
  assert.equal(h.captures.length, 1);
  assert.equal(h.recording(), false);
  assert.equal(h.options().autocapture, false);
  assert.equal(h.options().session_recording.maskAllInputs, true);
  h.api.trackEvent("download_link_ready", { provider: "envato" });
  assert.equal(h.captures[1].event, "download_link_ready");
  assert.equal(JSON.stringify(h.captures).includes("SECRET"), false);
  h.api.saveConsent(false, false);
  const count = h.captures.length;
  h.api.trackEvent("login");
  assert.equal(h.captures.length, count);
  assert.equal(h.options().before_send({ event: "$pageview", properties: {} }), null);
});

test("recordings stop on private routes and snapshots are rejected there", () => {
  const h = harness();
  h.api.syncAnalytics(config, choice(false, true), "/");
  assert.equal(h.recording(), true);
  h.location.pathname = "/payment";
  h.api.syncAnalytics(config, choice(false, true), "/payment");
  assert.equal(h.recording(), false);
  assert.equal(h.options().before_send({ event: "$snapshot", properties: {} }), null);
});
