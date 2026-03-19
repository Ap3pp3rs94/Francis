const test = require("node:test");
const assert = require("node:assert/strict");

const {
  DEFAULT_ORB_FOCUS_SIZE,
  buildOrbFocusCropRect,
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
