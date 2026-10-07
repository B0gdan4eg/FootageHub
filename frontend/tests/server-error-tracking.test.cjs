const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

function harness() {
  const sent = [];
  class PostHog {
    constructor(token, options) { this.options = options; }
    async captureExceptionImmediate(error) {
      sent.push(this.options.before_send({ event: "$exception", distinctId: "SECRET", properties: {
        $exception_list: [{ type: error.name, value: error.message, stacktrace: { frames: [] } }],
        headers: "SECRET", $session_id: "SECRET",
      } }));
    }
  }
  const exports = {};
  const context = vm.createContext({ require: () => ({ PostHog }), exports, Date, Map, Error, console,
    process: { env: { POSTHOG_PROJECT_TOKEN: "phc_fixture", APP_REVISION: "a".repeat(40) } },
  });
  const source = fs.readFileSync(path.join(__dirname, "../src/lib/server-error-tracking.ts"), "utf8");
  vm.runInContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, context);
  return { api: exports, sent };
}

test("server exception redaction drops request data, messages, and local variables", () => {
  const { api } = harness();
  const value = api.sanitizeServerError({ event: "$exception", distinctId: "SECRET", properties: {
    body: "SECRET", $exception_list: [{ type: "Error", value: "SECRET", stacktrace: { frames: [{
      filename: "/private/user/page.ts", function: "handler", lineno: 15,
      vars: { token: "SECRET" }, context_line: "SECRET", abs_path: "SECRET",
    }] } }],
  } });
  const text = JSON.stringify(value);
  assert.equal(text.includes("SECRET"), false);
  assert.equal(text.includes("private"), false);
  assert.equal(value.distinctId, "service:frontend");
  assert.equal(value.properties.$exception_list[0].stacktrace.frames[0].lineno, 15);
});

test("repeated server errors are limited and SDK receives only sanitized events", async () => {
  const { api, sent } = harness();
  for (let i = 0; i < 15; i++) await api.captureServerError(new Error("SECRET"));
  assert.equal(sent.length, 5);
  assert.equal(JSON.stringify(sent).includes("SECRET"), false);
});
