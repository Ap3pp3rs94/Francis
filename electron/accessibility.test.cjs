const test = require("node:test");
const assert = require("node:assert/strict");

const {
  DEFAULT_MOTION_MODE,
  buildAccessibilityState,
  normalizeMotionMode,
  resolveMotionMode,
} = require("./accessibility");

test("motion mode normalizes unknown values to system", () => {
  assert.equal(normalizeMotionMode("bad-mode"), DEFAULT_MOTION_MODE);
  assert.equal(normalizeMotionMode("REDUCE"), "reduce");
});

test("system motion resolves against reduced-motion preference", () => {
  const state = buildAccessibilityState({
    motionMode: "system",
    systemReducedMotion: true,
  });

  assert.equal(state.motionMode, "system");
  assert.equal(state.effectiveMotionMode, "reduce");
  assert.equal(state.reducedMotion, true);
});

test("explicit full motion overrides system reduction", () => {
  const resolved = resolveMotionMode("full", { systemReducedMotion: true });

  assert.equal(resolved.requested, "full");
  assert.equal(resolved.effective, "full");
  assert.equal(resolved.reduced, false);
});
