const test = require("node:test");
const assert = require("node:assert/strict");

const { buildProviderPosture, normalizeProviderId } = require("./provider-posture");

test("provider posture stays high when no provider path is declared", () => {
  const posture = buildProviderPosture({
    env: {},
    hudState: { mode: "managed", runtimeKind: "bundled", ready: true },
  });

  assert.equal(posture.severity, "high");
  assert.equal(posture.activeProviderId, null);
  assert.equal(posture.dependency, "inspect_only");
  assert.match(posture.summary, /no model provider/i);
});

test("provider posture supports local primary with governed remote fallback", () => {
  const posture = buildProviderPosture({
    env: {
      FRANCIS_PROVIDER: "ollama",
      FRANCIS_PROVIDER_FALLBACKS: "openai",
      OLLAMA_HOST: "http://127.0.0.1:11434",
      OPENAI_API_KEY: "redacted",
    },
    hudState: { mode: "managed", runtimeKind: "bundled", ready: true },
  });

  assert.equal(posture.severity, "low");
  assert.equal(posture.activeProviderId, "ollama");
  assert.equal(posture.fallbackProviderIds[0], "openai");
  assert.equal(posture.dependency, "hybrid");
  assert.match(posture.summary, /governed remote fallback/i);
  assert.equal(posture.modelRoles.fast, "llama3.1:8b");
  assert.equal(posture.modelRoles.heavy, "phi4:14b");
});

test("provider posture respects explicit fast and heavy model overrides", () => {
  const posture = buildProviderPosture({
    env: {
      FRANCIS_PROVIDER: "ollama",
      FRANCIS_OLLAMA_HOST: "http://127.0.0.1:11434",
      FRANCIS_OLLAMA_FAST_MODEL: "llama3.2:3b",
      FRANCIS_OLLAMA_HEAVY_MODEL: "phi4:14b-q6",
    },
    hudState: { mode: "managed", runtimeKind: "bundled", ready: true },
  });

  assert.equal(posture.modelRoles.fast, "llama3.2:3b");
  assert.equal(posture.modelRoles.heavy, "phi4:14b-q6");
  assert.ok(posture.cards.some((card) => card.label === "Fast Loop Model" && card.value === "llama3.2:3b"));
  assert.ok(posture.cards.some((card) => card.label === "Heavy Work Model" && card.value === "phi4:14b-q6"));
});

test("provider posture warns when remote primary has no fallback", () => {
  const posture = buildProviderPosture({
    env: {
      FRANCIS_PROVIDER: "openai",
      OPENAI_API_KEY: "redacted",
    },
    hudState: { mode: "managed", runtimeKind: "bundled", ready: true },
  });

  assert.equal(posture.severity, "medium");
  assert.equal(posture.activeProviderId, "openai");
  assert.equal(posture.fallbackSummary, "none");
  assert.match(posture.summary, /only active provider/i);
});

test("provider ids normalize aliases into canonical values", () => {
  assert.equal(normalizeProviderId("local"), "ollama");
  assert.equal(normalizeProviderId("llama.cpp"), "llamacpp");
  assert.equal(normalizeProviderId("claude"), "anthropic");
  assert.equal(normalizeProviderId("unknown"), null);
});
