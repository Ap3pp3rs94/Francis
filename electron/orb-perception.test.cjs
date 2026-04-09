const test = require("node:test");
const assert = require("node:assert/strict");

const {
  DEFAULT_ORB_FOCUS_SIZE,
  buildOrbEnvironmentGrounding,
  buildOrbFocusCropRect,
  normalizeOrbFocusedAccessibilityInfo,
  buildOrbTargetStability,
} = require("./orb-perception");

test("buildOrbFocusCropRect centers the cursor inside the captured display thumbnail", () => {
  const rect = buildOrbFocusCropRect({
    sourceWidth: 720,
    sourceHeight: 405,
    displayBounds: { x: 100, y: 40, width: 1600, height: 900 },
    cursorScreen: { x: 900, y: 490 },
  });

  assert.deepEqual(rect, {
    x: 262,
    y: 105,
    width: DEFAULT_ORB_FOCUS_SIZE,
    height: DEFAULT_ORB_FOCUS_SIZE,
  });
});

test("buildOrbFocusCropRect clamps the focus crop to the thumbnail edges", () => {
  const rect = buildOrbFocusCropRect({
    sourceWidth: 180,
    sourceHeight: 140,
    displayBounds: { x: -1920, y: 0, width: 1920, height: 1080 },
    cursorScreen: { x: -1920, y: 0 },
  });

  assert.deepEqual(rect, {
    x: 0,
    y: 0,
    width: 180,
    height: 140,
  });
});

test("buildOrbTargetStability marks a settled cursor target after a short dwell", () => {
  const stability = buildOrbTargetStability({
    nowMs: 1000,
    samples: [
      { x: 540, y: 320, at: 620 },
      { x: 548, y: 326, at: 760 },
      { x: 550, y: 328, at: 860 },
      { x: 551, y: 329, at: 940 },
    ],
  });

  assert.equal(stability.state, "settled");
  assert.ok(stability.dwellMs >= 180);
  assert.equal(stability.sampleCount, 4);
  assert.match(stability.summary, /settled/i);
});

test("buildOrbTargetStability marks a fast cursor pass as transient", () => {
  const stability = buildOrbTargetStability({
    nowMs: 1000,
    samples: [
      { x: 120, y: 120, at: 620 },
      { x: 240, y: 180, at: 760 },
      { x: 360, y: 240, at: 860 },
      { x: 520, y: 340, at: 960 },
    ],
  });

  assert.equal(stability.state, "transient");
  assert.ok(stability.travelPx > 120);
  assert.match(stability.summary, /transient/i);
});

test("normalizeOrbFocusedAccessibilityInfo shapes a focused UIA control into a stable shell contract", () => {
  const accessibility = normalizeOrbFocusedAccessibilityInfo({
    available: true,
    attached: true,
    name: "Search box",
    automationId: "SearchEditBox",
    controlType: "ControlType.Edit",
    localizedControlType: "edit",
    className: "SearchHost",
    processId: 9012,
    hasKeyboardFocus: true,
    enabled: true,
    offscreen: false,
    bounds: { x: 320, y: 180, width: 240, height: 36 },
  });

  assert.equal(accessibility.available, true);
  assert.equal(accessibility.attached, true);
  assert.equal(accessibility.label, "Search box");
  assert.equal(accessibility.controlType, "edit");
  assert.equal(accessibility.processId, 9012);
  assert.deepEqual(accessibility.bounds, { x: 320, y: 180, width: 240, height: 36 });
});

test("buildOrbEnvironmentGrounding promotes aligned accessibility, window, and visual evidence into grounded state", () => {
  const environment = buildOrbEnvironmentGrounding({
    nowMs: 5000,
    cursorScreen: { x: 540, y: 360 },
    displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
    foregroundWindow: {
      title: "Visual Studio Code",
      process: "Code.exe",
      pid: 701,
      bounds: { x: 120, y: 80, width: 1440, height: 900 },
    },
    accessibility: {
      available: true,
      attached: true,
      name: "Editor",
      controlType: "ControlType.Document",
      processId: 701,
      bounds: { x: 420, y: 220, width: 760, height: 520 },
    },
    targetStability: { state: "settled" },
    focusAttached: true,
    frameAttached: true,
    samples: [
      { key: "701|code.exe|visual studio code|120:80:1440:900", at: 2800 },
      { key: "701|code.exe|visual studio code|120:80:1440:900", at: 3900 },
    ],
  });

  assert.equal(environment.grounding.state, "grounded");
  assert.ok(environment.grounding.score >= 0.78);
  assert.equal(environment.primarySource, "accessibility");
  assert.equal(environment.sources.window_metadata.in_window, true);
  assert.equal(environment.sources.accessibility.cursor_inside, true);
  assert.equal(environment.grounding.continuity_state, "anchored");
});

test("buildOrbEnvironmentGrounding marks detached state when cursor leaves the grounded foreground path", () => {
  const environment = buildOrbEnvironmentGrounding({
    nowMs: 6000,
    cursorScreen: { x: 1800, y: 900 },
    displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
    foregroundWindow: {
      title: "Visual Studio Code",
      process: "Code.exe",
      pid: 701,
      bounds: { x: 120, y: 80, width: 960, height: 700 },
    },
    accessibility: {
      available: true,
      attached: true,
      name: "Editor",
      controlType: "ControlType.Document",
      processId: 701,
      bounds: { x: 180, y: 160, width: 800, height: 540 },
    },
    targetStability: { state: "tracking" },
    focusAttached: true,
    frameAttached: true,
  });

  assert.equal(environment.grounding.state, "detached");
  assert.equal(environment.grounding.invalidation_reason, "cursor_left_foreground_window");
  assert.equal(environment.sources.window_metadata.in_window, false);
});
