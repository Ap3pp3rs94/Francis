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
    startupProfile: { requested: "operator" },
  });

  assert.equal(posture.mode, "restricted");
  assert.equal(posture.continuityTrust, "unsafe");
  assert.equal(posture.pointerPosture, "interactive_only");
  assert.equal(posture.recommendedStartupProfile, "core_only");
});
