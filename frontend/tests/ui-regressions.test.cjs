/* eslint-disable @typescript-eslint/no-require-imports -- Node test harness. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

function loadModule(name, globals = {}) {
  const filename = path.resolve(__dirname, "../src/lib", name);
  const exports = {};
  const source = fs.readFileSync(filename, "utf8");
  const requireLocal = request => request.startsWith(".")
    ? loadModule(path.relative(path.resolve(__dirname, "../src/lib"), path.resolve(path.dirname(filename), request + ".ts")), globals)
    : require(request);
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  } }).outputText, { exports, require: requireLocal, URL, Date, ...globals });
  return exports;
}

const { nextTranslation } = loadModule("translation-state.ts");
const { translateText } = loadModule("language.tsx");
const identity = value => value;

test("payment amounts and Latin plan names follow React updates in both languages", () => {
  for (const translate of [identity, translateText]) {
    for (const sequence of [["Standard", "Lite", "Pro", "Standard"], ["$10.99", "$4.99", "$21.99", "$10.99"], ["77", "76", "75", "0"]]) {
      let state;
      for (const value of sequence) {
        state = nextTranslation(value, state, translate);
        assert.equal(state.rendered, value);
        state = nextTranslation(state.rendered, state, translate);
        assert.equal(state.source, value);
      }
    }
  }
});

test("dynamic translated text updates in RU and EN without restoring old values", () => {
  let state = nextTranslation("Оплатить $10.99", undefined, translateText);
  assert.equal(state.rendered, "Pay $10.99");
  state = nextTranslation("Оплатить $4.99", state, translateText);
  assert.equal(state.rendered, "Pay $4.99");
  state = nextTranslation(state.rendered, state, identity);
  assert.equal(state.rendered, "Оплатить $4.99");
  state = nextTranslation("Оплатить $21.99", state, identity);
  assert.equal(state.rendered, "Оплатить $21.99");
  state = nextTranslation(state.rendered, state, translateText);
  assert.equal(state.rendered, "Pay $21.99");
});

test("countdown and empty text remain dynamic", () => {
  let state;
  for (const value of ["59", "58", "10", "09", "00", ""]) {
    state = nextTranslation(value, state, translateText);
    assert.equal(state.rendered, value);
  }
});

test("dashboard balance hint has an exact translation", () => {
  assert.equal(translateText("Пополни баланс на странице оплаты"), "Top up on the payment page");
});

const { safeReturnPath } = loadModule("navigation.ts");
test("post-login navigation preserves plan but rejects external and unsafe redirects", () => {
  assert.equal(safeReturnPath("/payment?plan=monthly_50"), "/payment?plan=monthly_50");
  for (const value of [null, "https://evil.test", "//evil.test", "/\\evil.test", "/auth", "javascript:alert(1)", "/%2f%2fevil.test", "/dashboard\n"]) {
    assert.equal(safeReturnPath(value), "/dashboard");
  }
});

function intentHarness() {
  const values = new Map();
  const storage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  return { api: loadModule("download-intent.ts", { sessionStorage: storage }), values };
}

test("asset validation accepts supported URLs and rejects malformed or spoofed hosts", () => {
  const { api } = intentHarness();
  for (const value of ["elements.envato.com/example", "https://www.freepik.com/premium-psd/example.htm", "https://www.magnific.com/ru/example", "https://motionarray.com/templates/example/"]) {
    assert.ok(api.normalizeAssetUrl(value)?.startsWith("https://"));
  }
  for (const value of ["", "not-a-valid-url", "https://freepik.com.evil.test/file", "https://evilfreepik.com/file", "https://freepik.com@evil.test/file", "https://user:pass@freepik.com/file", "ftp://freepik.com/file", "https://freepik.com/", "javascript:alert(1)"]) {
    assert.equal(api.normalizeAssetUrl(value), null);
  }
});

test("pending asset survives until consumed, expires and fails closed", () => {
  const { api, values } = intentHarness();
  const url = "https://www.freepik.com/file.htm?search=example#preview";
  assert.equal(api.saveDownloadIntent(url), true);
  assert.equal(api.takeDownloadIntent(), url);
  assert.equal(api.takeDownloadIntent(), "");
  values.set("fh_pending_asset", JSON.stringify({ url, expires: Date.now() - 1 }));
  assert.equal(api.takeDownloadIntent(), "");
  values.set("fh_pending_asset", "broken");
  assert.equal(api.takeDownloadIntent(), "");
  const blocked = loadModule("download-intent.ts", { sessionStorage: { setItem() { throw Error("blocked"); }, getItem() { throw Error("blocked"); } } });
  assert.equal(blocked.saveDownloadIntent(url), false);
  assert.equal(blocked.takeDownloadIntent(), "");
});

test("history filenames exclude query and hash tracking and tolerate malformed encoding", () => {
  const { api } = intentHarness();
  assert.equal(api.assetFileName("https://freepik.com/test.htm?uuid=secret#tracking=secret"), "test.htm");
  assert.equal(api.assetFileName("https://freepik.com/test.htm#tracking=secret"), "test.htm");
  assert.equal(api.assetFileName("https://freepik.com/%ZZ#secret"), "%ZZ");
});
