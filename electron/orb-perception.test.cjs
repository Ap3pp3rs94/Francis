const test = require("node:test");
const assert = require("node:assert/strict");

const {
  DEFAULT_ORB_FOCUS_SIZE,
  buildOrbFocusCropRect,
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
