const test = require("node:test");
const assert = require("node:assert/strict");

const {
  DEFAULT_CONTRAST_MODE,
  DEFAULT_DENSITY_MODE,
  DEFAULT_MOTION_MODE,
  buildAccessibilityState,
  normalizeContrastMode,
  normalizeDensityMode,
  normalizeMotionMode,
  resolveContrastMode,
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

test("contrast mode normalizes unknown values to system", () => {
  assert.equal(normalizeContrastMode("bad-mode"), DEFAULT_CONTRAST_MODE);
  assert.equal(normalizeContrastMode("HIGH"), "high");
});

test("density mode normalizes unknown values to comfortable", () => {
  assert.equal(normalizeDensityMode("bad-mode"), DEFAULT_DENSITY_MODE);
  assert.equal(normalizeDensityMode("COMPACT"), "compact");
});

test("system contrast resolves against high-contrast preference", () => {
  const resolved = resolveContrastMode("system", { systemHighContrast: true });

  assert.equal(resolved.requested, "system");
  assert.equal(resolved.effective, "high");
  assert.equal(resolved.high, true);
});

test("accessibility state carries keyboard and density posture", () => {
  const state = buildAccessibilityState({
    motionMode: "reduce",
    contrastMode: "high",
    densityMode: "compact",
    shortcuts: {
      toggleOverlay: "Ctrl+Shift+Alt+F",
      toggleClickThrough: "Ctrl+Shift+Alt+C",
    },
  });

  assert.equal(state.reducedMotion, true);
  assert.equal(state.highContrast, true);
  assert.equal(state.densityMode, "compact");
  assert.equal(state.keyboardFirst, true);
  assert.match(state.stressControls, /Ctrl\+Shift\+Alt\+C/);
  assert.ok(Array.isArray(state.items));
});
