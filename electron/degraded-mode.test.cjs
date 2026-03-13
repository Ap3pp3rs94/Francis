const test = require("node:test");
const assert = require("node:assert/strict");

const { buildDegradedModePosture } = require("./degraded-mode");

test("degraded mode is nominal when shell posture is clean", () => {
  const posture = buildDegradedModePosture({
    preflight: { blocked: 0, attention: 0 },
    migration: { blocked: 0, attention: 0 },
    update: { pendingNotice: false },
    recovery: { needed: false },
    hud: { mode: "managed", ready: true },
    provider: { severity: "low", activeProviderLabel: "Ollama" },
    startupProfile: { requested: "operator" },
  });

  assert.equal(posture.mode, "nominal");
  assert.equal(posture.continuityTrust, "current");
  assert.equal(posture.recommendedStartupProfile, "operator");
});

test("degraded mode becomes reduced when continuity needs review", () => {
  const posture = buildDegradedModePosture({
    preflight: { blocked: 0, attention: 1 },
    migration: { blocked: 0, attention: 1 },
    update: { pendingNotice: true },
    recovery: { needed: false },
    hud: { mode: "managed", ready: true },
    provider: { severity: "low", activeProviderLabel: "Ollama" },
    startupProfile: { requested: "quiet" },
  });

  assert.equal(posture.mode, "reduced");
  assert.equal(posture.continuityTrust, "review");
  assert.match(posture.summary, /pending review|review/i);
});

test("degraded mode becomes restricted when blocked posture is present", () => {
  const posture = buildDegradedModePosture({
    preflight: { blocked: 1, attention: 0 },
    migration: { blocked: 1, attention: 0 },
    update: { pendingNotice: false },
    recovery: { needed: true },
    hud: { mode: "crashed", ready: false },
    provider: { severity: "high", activeProviderLabel: "none", summary: "No model provider is configured." },
    startupProfile: { requested: "operator" },
  });

  assert.equal(posture.mode, "restricted");
  assert.equal(posture.continuityTrust, "unsafe");
  assert.equal(posture.pointerPosture, "interactive_only");
  assert.equal(posture.recommendedStartupProfile, "core_only");
});

test("degraded mode becomes reduced when provider posture is not current", () => {
  const posture = buildDegradedModePosture({
    preflight: { blocked: 0, attention: 0 },
    migration: { blocked: 0, attention: 0 },
    update: { pendingNotice: false },
    recovery: { needed: false },
    hud: { mode: "managed", ready: true },
    provider: {
      severity: "medium",
      activeProviderLabel: "OpenAI",
      summary: "OpenAI is the only active provider. Provider failure will narrow model-backed work immediately.",
    },
    startupProfile: { requested: "operator" },
  });

  assert.equal(posture.mode, "reduced");
  assert.match(posture.summary, /provider/i);
  assert.ok(posture.restrictions.some((entry) => /model-backed execution/i.test(entry)));
});
