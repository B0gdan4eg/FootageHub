/* eslint-disable @typescript-eslint/no-require-imports -- Node's CommonJS browser harness. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const path = require("node:path");
const base = process.env.ANALYTICS_TEST_URL || "http://127.0.0.1:3100";

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      const context = await browser.newContext({ viewport, locale: "en-US" });
      const page = await context.newPage();
      // Development-only overlay is absent in production and overlaps the cookie button.
      page.on("domcontentloaded", () => page.addStyleTag({ content: "nextjs-portal { display: none !important; }" }).catch(() => {}));
      const errors = [];
      const vendors = [];
      page.on("pageerror", error => errors.push(error.message));
      await context.route("**/*", async route => {
        const url = new URL(route.request().url());
        if (/google-analytics\.com|googletagmanager\.com|posthog\.com|posthog-assets\.com/.test(url.hostname)) {
          vendors.push(url.hostname);
          return route.fulfill({ contentType: "application/javascript", body: "/* analytics isolated during regression tests */" });
        }
        if (url.pathname === "/analytics-config") return route.fulfill({ json: {
          ga4: "G-TEST123456", posthog: "phc_test123", posthogHost: "https://eu.i.posthog.com",
        } });
        if (url.pathname.startsWith("/api/")) {
          const fixtures = {
            "/api/payments/plans": { monthly_50: { name: "Lite", price: 400 }, monthly_150: { name: "Standard", price: 900 }, monthly_400: { name: "Pro", price: 1800 } },
            "/api/auth/qr/start": { token: "PRIVATE_QR_TOKEN", deeplink: "https://t.me/FootageHub_bot?start=PRIVATE_QR_TOKEN", expires_at: new Date(Date.now() + 300000).toISOString() },
            "/api/users/me": { id: 1, username: "PRIVATE_USERNAME", credits: 5, ai_credits: 0, role: "user" },
            "/api/users/me/downloads": [], "/api/users/me/subscriptions": [],
          };
          if (url.pathname === "/api/downloads/") return route.fulfill({ status: 400, json: { detail: "PRIVATE_ASSET_ERROR" } });
          if (url.pathname === "/api/payments/create") return route.fulfill({ status: 400, json: { detail: "PRIVATE_CHECKOUT_ERROR" } });
          if (url.pathname.startsWith("/api/auth/qr/status/")) return route.fulfill({ json: { status: "CONFIRMED", access_token: "PRIVATE_JWT_TOKEN" } });
          return route.fulfill({ json: fixtures[url.pathname] || { status: "PENDING" } });
        }
        return route.continue();
      });
      await page.goto(base + "/en", { waitUntil: "domcontentloaded", timeout: 120000 });
      const reject = page.getByRole("button", { name: "Reject", exact: true });
      await reject.waitFor({ timeout: 120000 });
      assert.equal(vendors.length, 0, "vendor loaded before consent");
      const region = page.getByRole("region", { name: "Privacy preferences" });
      assert.deepEqual(await region.getByRole("button").allTextContents(), ["Accept", "Reject", "Customize"]);
      const acceptStyle = await region.getByRole("button", { name: "Accept", exact: true }).evaluate(button => ({ background: getComputedStyle(button).backgroundColor, color: getComputedStyle(button).color }));
      assert.deepEqual(acceptStyle, { background: "rgb(45, 107, 255)", color: "rgb(255, 255, 255)" });
      assert.notEqual(await reject.evaluate(button => getComputedStyle(button).backgroundColor), acceptStyle.background);
      assert.equal(await region.getByRole("checkbox").count(), 0);
      const buttons = await region.getByRole("button").all();
      const boxes = await Promise.all(buttons.map(button => button.boundingBox()));
      assert(boxes[0].y + boxes[0].height <= boxes[1].y && boxes[1].y + boxes[1].height <= boxes[2].y);
      await page.getByRole("button", { name: "Customize", exact: true }).click();
      assert.equal(await region.getByRole("checkbox").count(), 2);
      for (const checkbox of await region.getByRole("checkbox").all()) assert(await checkbox.isChecked());
      assert.equal(vendors.length, 0, "opening preset preferences must not enable analytics");
      await page.screenshot({ path: path.join(__dirname, `../../deliverables/analytics-settings-${viewport.width}.png`), fullPage: false });
      await page.getByRole("button", { name: "Customize", exact: true }).click();
      const box = await region.boundingBox();
      assert(box.x >= 0 && box.y >= 0 && box.x + box.width <= viewport.width);
      assert(box.y + box.height <= viewport.height);
      await page.screenshot({ path: path.join(__dirname, `../../deliverables/analytics-${viewport.width}.png`), fullPage: false });
      await reject.click();
      await page.reload({ waitUntil: "domcontentloaded" });
      await page.getByRole("button", { name: "Privacy preferences", exact: true }).waitFor();
      assert.equal(vendors.length, 0, "rejection not persisted");
      await page.getByRole("button", { name: "Privacy preferences", exact: true }).click();
      await page.getByRole("button", { name: "Customize", exact: true }).click();
      for (const checkbox of await region.getByRole("checkbox").all()) assert.equal(await checkbox.isChecked(), false, "saved refusal must be respected");
      await page.getByRole("button", { name: "Customize", exact: true }).click();
      await page.getByRole("button", { name: "Accept", exact: true }).click();
      await page.waitForFunction(() => document.getElementById("fh-ga4"));
      assert.equal(vendors.filter(host => host.includes("googletagmanager")).length, 1);
      await page.locator('a[href="/payment"]').first().click();
      await page.waitForURL("**/payment");
      await page.getByRole("button", { name: /Pay \$/ }).waitFor({ timeout: 60000 });
      assert.equal(vendors.filter(host => host.includes("clarity")).length, 0);
      const isDocument = await page.evaluate(() => performance.getEntriesByType("navigation")[0].name.endsWith("/payment"));
      assert.equal(isDocument, true, "private page must use a new document after replay");
      await context.addCookies([{ name: "access_token", value: "PRIVATE_JWT_TOKEN", url: base }]);
      await page.getByRole("button", { name: /Lite/ }).click();
      await page.getByRole("button", { name: /Pay \$/ }).click();
      await page.getByText("PRIVATE_CHECKOUT_ERROR").waitFor();
      const events = await page.evaluate(() => (window.dataLayer || []).map(v => Array.from(v)).filter(v => v[0] === "event"));
      assert(events.some(v => v[1] === "begin_checkout"));
      assert(events.some(v => v[1] === "checkout_error"));
      assert(!events.some(v => v[1] === "purchase"));
      assert(!JSON.stringify(events).includes("PRIVATE_"));
      assert.equal(events.filter(v => v[1] === "page_view").length, 1);
      await context.clearCookies();
      await page.goto(base + "/auth?test=PRIVATE_QUERY", { waitUntil: "domcontentloaded" });
      await page.waitForURL("**/dashboard", { timeout: 60000 });
      await page.getByPlaceholder("https://elements.envato.com/...").fill("https://www.freepik.com/premium-psd/PRIVATE_ASSET.htm?token=PRIVATE_LINK");
      await page.locator('button[type="submit"]').click();
      await page.getByText("PRIVATE_ASSET_ERROR").waitFor();
      const privateEvents = await page.evaluate(() => (window.dataLayer || []).map(v => Array.from(v)).filter(v => v[0] === "event"));
      assert(privateEvents.some(v => v[1] === "login"));
      assert(privateEvents.some(v => v[1] === "download_requested"));
      assert(privateEvents.some(v => v[1] === "download_error"));
      assert(!JSON.stringify(privateEvents).includes("PRIVATE_"));
      assert.equal(await page.locator("#fh-clarity").count(), 0);
      await page.getByRole("button", { name: "Privacy preferences", exact: true }).click();
      await Promise.all([
        page.waitForEvent("load"),
        page.getByRole("button", { name: "Reject", exact: true }).click(),
      ]);
      await page.getByRole("button", { name: "Privacy preferences", exact: true }).waitFor();
      assert.equal(await page.locator("#fh-ga4").count(), 0);
      assert.deepEqual(errors, []);
      console.log(`PASS ${viewport.width}px: consent, persistence, scripts, private navigation, checkout, login, downloads, withdrawal, no browser errors`);
      await context.close();
    }
    const context = await browser.newContext({ viewport: { width: 320, height: 700 }, locale: "ru-RU" });
    const page = await context.newPage();
    page.on("domcontentloaded", () => page.addStyleTag({ content: "nextjs-portal { display: none !important; }" }).catch(() => {}));
    const vendors = [];
    await context.route(/google-analytics\.com|googletagmanager\.com|posthog\.com|posthog-assets\.com/, route => {
      vendors.push(new URL(route.request().url()).hostname);
      return route.fulfill({ contentType: "application/javascript", body: "/* isolated analytics */" });
    });
    await context.route("**/analytics-config", route => route.fulfill({ json: {
      ga4: "G-TEST123456", posthog: "phc_test123", posthogHost: "https://eu.i.posthog.com",
    } }));
    await page.goto(base + "/", { waitUntil: "domcontentloaded" });
    const region = page.getByRole("region", { name: "Настройки конфиденциальности" });
    await region.waitFor();
    assert.deepEqual(await region.getByRole("button").allTextContents(), ["Принять", "Отклонить", "Настроить"]);
    await page.getByRole("button", { name: "Настроить", exact: true }).click();
    await page.getByRole("checkbox", { name: "Запись главной страницы (PostHog)" }).uncheck();
    assert.equal(vendors.length, 0);
    const box = await region.boundingBox();
    assert(box.x >= 0 && box.x + box.width <= 320 && box.y >= 0 && box.y + box.height <= 700);
    await page.screenshot({ path: path.join(__dirname, "../../deliverables/analytics-settings-ru-320.png"), fullPage: false });
    await page.getByRole("button", { name: "Принять", exact: true }).click();
    await page.waitForFunction(() => !!document.getElementById("fh-ga4"));
    assert.equal(await page.locator("#fh-clarity").count(), 0);
    const saved = await page.evaluate(() => JSON.parse(localStorage.getItem("fh_analytics_consent_v2")));
    assert.equal(saved.statistics, true);
    assert.equal(saved.replay, false);
    console.log("PASS RU 320px: translated buttons, settings fit, selected preferences saved, no PostHog replay after opting out");
    await context.close();
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
